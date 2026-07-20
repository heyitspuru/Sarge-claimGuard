"""Plain-Python pipeline orchestrator: chains the four agents with retries + an audit log."""

from collections.abc import Callable
from dataclasses import dataclass

from claimguard import fraud
from claimguard.agents.coder import assign_codes
from claimguard.agents.packager import package
from claimguard.agents.submitter import submit
from claimguard.agents.summarizer import summarize
from claimguard.models import DischargeRecord

# ponytail: linear step list; LangGraph only if Phase 2 negotiation loop outgrows it.


@dataclass
class PipelineDeps:
    llm: Callable
    retrieve: Callable
    store: dict
    audit: Callable[[dict], None]
    # §9-7: consent(record_id) -> True if withdrawn. Checked BETWEEN steps, not once at
    # entry, so a withdrawal arriving mid-pipeline still halts the claim.
    consent: Callable[[str], bool] | None = None
    # §9-10: (abha_id, admission_date) -> record_id, for duplicate flagging.
    admission_index: dict | None = None
    # Closes the loop: (record, submission_result) -> AppealResult | None. Supplied by
    # appeal.make_appeal_handler so the orchestrator stays ignorant of clause shapes.
    appeal: Callable | None = None


def _run_step(record_id: str, step: str, audit: Callable[[dict], None],
              fn: Callable, detail: Callable = lambda result: {}):
    """Run fn() with one retry. Audits start, each error, and the final ok. Raises on double failure."""
    audit({"record_id": record_id, "step": step, "status": "start", "detail": {}})
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            result = fn()
        except Exception as exc:  # noqa: BLE001 - any agent/LLM failure is retryable here
            last_exc = exc
            audit({"record_id": record_id, "step": step, "status": "error",
                   "detail": {"error": str(exc), "attempt": attempt + 1}})
            continue
        audit({"record_id": record_id, "step": step, "status": "ok", "detail": detail(result)})
        return result
    raise last_exc


def run_claim(record: DischargeRecord, deps: PipelineDeps) -> dict:
    record_id = record.record_id

    def _error(icd_codes=None, packaging=None):
        return {"record_id": record_id, "final_status": "error", "icd_codes": icd_codes or [],
                "packaging": packaging, "outcome": None}

    def _halted(step: str, icd_codes=None):
        deps.audit({"record_id": record_id, "step": step, "status": "halted",
                    "detail": {"reason": "consent_withdrawn"}})
        return {"record_id": record_id, "final_status": "consent_withdrawn",
                "icd_codes": icd_codes or [], "packaging": None, "outcome": None}

    def _withdrawn() -> bool:
        return deps.consent is not None and deps.consent(record_id)

    if _withdrawn():
        return _halted("intake")

    try:
        summary = _run_step(record_id, "summarize", deps.audit,
                             lambda: summarize(record, llm=deps.llm),
                             detail=lambda s: {"primary_diagnosis": s.primary_diagnosis})
    except Exception:
        return _error()

    try:
        codes = _run_step(record_id, "code", deps.audit,
                           lambda: assign_codes(summary, deps.retrieve, llm=deps.llm),
                           detail=lambda cs: {"icd_codes": [c.icd_code for c in cs]})
    except Exception:
        return _error()

    icd_codes = [c.icd_code for c in codes]

    if _withdrawn():
        return _halted("package", icd_codes)

    try:
        pkg = _run_step(record_id, "package", deps.audit,
                         lambda: package(record, summary, codes),
                         detail=lambda p: {"status": p.status})
    except Exception:
        return _error(icd_codes)

    # §9-10: advisory only — a flagged claim still proceeds, it just carries the flag
    # so a human can look. Blocking here would deny legitimate resubmissions.
    if deps.admission_index is not None:
        pkg.flags = fraud.check(record, deps.admission_index)
        if pkg.flags:
            deps.audit({"record_id": record_id, "step": "fraud_check",
                        "status": "flagged", "detail": {"flags": pkg.flags}})

    if pkg.status != "ready":
        return {"record_id": record_id, "final_status": pkg.status, "icd_codes": icd_codes,
                "packaging": pkg.status, "outcome": None, "flags": pkg.flags}

    if _withdrawn():
        return _halted("submit", icd_codes)

    try:
        result = _run_step(record_id, "submit", deps.audit,
                            lambda: submit(pkg, deps.store),
                            detail=lambda r: {"outcome": r.outcome})
    except Exception:
        return _error(icd_codes, pkg.status)

    out = {"record_id": record_id, "final_status": "adjudicated", "icd_codes": icd_codes,
           "packaging": pkg.status, "outcome": result.outcome, "flags": pkg.flags,
           "appeal": None}

    # A denial nobody appeals is the failure mode this project exists to fix. An appeal
    # failing must not fail the claim, though — the adjudication already happened.
    if deps.appeal is not None and result.outcome in ("partial", "rejected"):
        try:
            appeal = _run_step(record_id, "appeal", deps.audit,
                                lambda: deps.appeal(record, result),
                                detail=lambda a: {"status": a.status if a else "not_applicable",
                                                  "citations": len(a.citations) if a else 0})
        except Exception:
            appeal = None
        out["appeal"] = appeal.model_dump() if appeal else None

    return out
