"""Run the eval harness over a golden directory (Task 5 layout)."""

import json
from collections.abc import Callable
from pathlib import Path

from claimguard.agents.packager import package
from claimguard.eval.metrics import hierarchical_f1
from claimguard.models import CodedDiagnosis, DischargeRecord, DischargeSummary
from claimguard.orchestrator import PipelineDeps, run_claim

Pipeline = Callable[[dict], dict]


def make_pipeline(retrieve: Callable, llm: Callable) -> Pipeline:
    """Adapt run_claim to the eval Pipeline contract: record dict -> {"icd_codes", "packaging"}."""

    def pipeline(record_dict: dict) -> dict:
        record = DischargeRecord.model_validate(record_dict)
        deps = PipelineDeps(llm=llm, retrieve=retrieve, store={}, audit=lambda e: None)
        result = run_claim(record, deps)
        return {"icd_codes": result["icd_codes"], "packaging": result["packaging"] or "error"}

    return pipeline


def run_eval(golden_dir: Path, pipeline: Pipeline | None = None) -> dict:
    golden_dir = Path(golden_dir)
    files = sorted(golden_dir.glob("*.json"))

    f1_scores = []
    packaging_hits = 0
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        record = payload["record"]
        answer_key = payload["answer_key"]

        if pipeline is None:
            pred = {"icd_codes": [], "packaging": "ready"}
        else:
            pred = pipeline(record)

        f1_scores.append(hierarchical_f1(pred["icd_codes"], answer_key["icd_codes"]))
        if pred["packaging"] == answer_key["expected_packaging"]:
            packaging_hits += 1

    n = len(files)
    return {
        "n": n,
        "coding_f1": sum(f1_scores) / n if n else 0.0,
        "packaging_validity": packaging_hits / n if n else 0.0,
        "grounding_rate": None,
    }


def run_packaging_check(golden_dir: Path) -> dict:
    """Measure the Packager IN ISOLATION, with no LLM and no coder in the loop.

    For each golden record, builds a DischargeSummary directly from the record fields
    and a list of CodedDiagnosis directly from the answer key's icd_codes (confidence=1.0,
    needs_review=False — i.e. "assume the coder got it right and was confident"), then calls
    `package()` and compares the resulting status to the golden `expected_packaging`.

    Scope note: records whose `expected_packaging` is "needs_review" are EXCLUDED. Those
    golden records earn "needs_review" because the *scenario* makes the coder low-confidence
    (vague_dx) — that's a coder-confidence property, not a packager property. Since this check
    feeds confident (needs_review=False) codes for every record, the packager would return
    "ready" for those, which is not a packager bug, just out of scope for what's being isolated
    here. This function therefore only scores the "ready" (complete docs) and "rejected"
    (missing docs) subset, where the expected outcome is fully decidable from documents + codes
    alone — and the packager MUST hit 1.0 there for the CLAUDE.md packaging-validity DoD gate to
    be honestly demonstrable offline.
    """
    golden_dir = Path(golden_dir)
    files = sorted(golden_dir.glob("*.json"))

    hits = 0
    n = 0
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        answer_key = payload["answer_key"]
        expected = answer_key["expected_packaging"]
        if expected == "needs_review":
            continue

        record = DischargeRecord.model_validate(payload["record"])
        summary = DischargeSummary(
            record_id=record.record_id,
            primary_diagnosis=record.diagnosis_text,
            secondary_diagnoses=[],
            procedures=record.procedures,
            medications=record.medications,
            admission_course=record.clinical_notes,
            source_fields={},
        )
        codes = [
            CodedDiagnosis(icd_code=code, description="", confidence=1.0, needs_review=False)
            for code in answer_key["icd_codes"]
        ]

        pkg = package(record, summary, codes)
        n += 1
        if pkg.status == expected:
            hits += 1

    return {"n": n, "packaging_validity": hits / n if n else 0.0}


def print_report(report: dict) -> None:
    print("ClaimGuard eval report")
    print("-----------------------")
    print(f"{'n records':<20} {report['n']}")
    print(f"{'coding_f1':<20} {report['coding_f1']:.3f}")
    print(f"{'packaging_validity':<20} {report['packaging_validity']:.3f}")
    grounding = report["grounding_rate"]
    print(f"{'grounding_rate':<20} {'n/a (Phase 2)' if grounding is None else f'{grounding:.3f}'}")
