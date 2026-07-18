"""Integration test: run_claim end to end over real data/golden records, with a
real ICD retriever (data/icd/icd10.csv) and a scripted fake LLM (no network, no
real model calls) standing in for the Gemini provider.
"""

import json
from pathlib import Path

from claimguard.icd import InMemoryRetriever, load_csv
from claimguard.llm import embed
from claimguard.models import DischargeRecord
from claimguard.orchestrator import PipelineDeps, run_claim

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "data" / "golden"
ICD_CSV = Path(__file__).resolve().parents[2] / "data" / "icd" / "icd10.csv"

RETRIEVER = InMemoryRetriever(load_csv(ICD_CSV), embed)


def _load_golden_by_packaging() -> dict[str, dict]:
    """First golden record found for each expected_packaging value ("ready",
    "rejected", "needs_review"), scanning data/golden in filename order."""
    found: dict[str, dict] = {}
    for path in sorted(GOLDEN_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        status = payload["answer_key"]["expected_packaging"]
        found.setdefault(status, payload)
        if len(found) == 3:
            break
    return found


GOLDEN = _load_golden_by_packaging()


def _first_candidate_code(prompt: str) -> str:
    # coder.py builds the prompt as "Candidates:\n{code} — {description}\n..."
    return prompt.splitlines()[1].split(" — ")[0]


def _make_fake_llm(record: DischargeRecord, confidence: float):
    """Scripted fake keyed by system prompt content (summarizer vs coder).

    The coder branch echoes back the *first retrieved candidate* rather than the
    golden answer-key code: the mock embed function (claimguard.llm._mock_embed)
    is a deterministic hash, not a semantic embedding, so it won't reliably surface
    the true ICD code in the top-k — same limitation the real pipeline has without
    a real embedding model. Using a real candidate keeps assign_codes' by_code
    lookup honest instead of special-casing the test.
    """

    def fake(prompt, system="", tier="fast", json_schema=None):
        if "clinical summarizer" in system:
            return {
                "primary_diagnosis": record.diagnosis_text,
                "secondary_diagnoses": [],
                "procedures": record.procedures,
                "medications": record.medications,
                "admission_course": record.clinical_notes,
            }
        if "Assign ICD-10" in system:
            return {"codes": [{"icd_code": _first_candidate_code(prompt), "confidence": confidence}]}
        raise AssertionError(f"unscripted system prompt: {system!r}")

    return fake


def _assert_audit_replayable(events: list[dict]) -> None:
    """Every step that started reaches a terminal ok/error, in order, no
    interleaving of different steps' events."""
    open_steps: list[str] = []
    for e in events:
        if e["status"] == "start":
            open_steps.append(e["step"])
        elif e["status"] in ("ok", "error"):
            assert open_steps and open_steps[-1] == e["step"], (
                f"terminal '{e['status']}' for step {e['step']!r} without a matching start"
            )
            if e["status"] == "ok":
                open_steps.pop()
            # "error" may be followed by a retry (another "start" for the same step)
            # or be the final event — both are valid, handled below.
        else:
            raise AssertionError(f"unknown audit status: {e['status']!r}")
    for step in open_steps:
        assert events[-1]["step"] == step and events[-1]["status"] == "error", (
            f"step {step!r} never reached a terminal event"
        )


def test_ready_record_reaches_adjudicated():
    payload = GOLDEN["ready"]
    record = DischargeRecord.model_validate(payload["record"])
    events: list[dict] = []
    deps = PipelineDeps(llm=_make_fake_llm(record, 0.95), retrieve=RETRIEVER, store={},
                         audit=events.append)

    result = run_claim(record, deps)

    assert result["final_status"] == "adjudicated"
    assert result["packaging"] == "ready"
    assert record.record_id in deps.store
    _assert_audit_replayable(events)


def test_rejected_record_never_reaches_submit():
    payload = GOLDEN["rejected"]
    record = DischargeRecord.model_validate(payload["record"])
    events: list[dict] = []
    deps = PipelineDeps(llm=_make_fake_llm(record, 0.95), retrieve=RETRIEVER, store={},
                         audit=events.append)

    result = run_claim(record, deps)

    assert result["final_status"] == "rejected"
    assert result["packaging"] == "rejected"
    assert deps.store == {}
    assert not any(e["step"] == "submit" for e in events)
    _assert_audit_replayable(events)


def test_low_confidence_record_needs_review():
    payload = GOLDEN["needs_review"]
    record = DischargeRecord.model_validate(payload["record"])
    events: list[dict] = []
    deps = PipelineDeps(llm=_make_fake_llm(record, 0.4), retrieve=RETRIEVER, store={},
                         audit=events.append)

    result = run_claim(record, deps)

    assert result["final_status"] == "needs_review"
    assert result["packaging"] == "needs_review"
    assert deps.store == {}
    assert not any(e["step"] == "submit" for e in events)
    _assert_audit_replayable(events)
