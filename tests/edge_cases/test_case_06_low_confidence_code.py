"""Edge case Sec9-6 (CLAUDE.md hard rule): a low-confidence code must never
reach the submitter. Runs the full orchestrator (not just the packager) to
prove the store stays empty end to end.
"""

from claimguard.icd import IcdEntry
from claimguard.models import DischargeRecord, Insurance, Patient
from claimguard.orchestrator import PipelineDeps, run_claim


def _record(**kw):
    base = dict(
        record_id="R9003",
        patient=Patient(name="Test Patient", age=40, sex="F", abha_id="00-0000-0000-0000"),
        admission_date="2026-01-01", discharge_date="2026-01-03",
        claim_type="cashless", specialty="general_surgery",
        diagnosis_text="Acute appendicitis", procedures=["Laparoscopic appendectomy"],
        medications=["Inj Ceftriaxone 1g IV BD"], clinical_notes="Uneventful recovery.",
        documents=["discharge_summary", "final_bill", "preauth_form", "id_proof"],
        insurance=Insurance(insurer_id="INS1", plan_id="P1", policy_number="POL1",
                             sum_insured=500000, claimed_amount=80000),
    )
    return DischargeRecord(**(base | kw))


def _fake_llm(prompt, system="", tier="fast", json_schema=None):
    if "clinical summarizer" in system:
        return {
            "primary_diagnosis": "Acute appendicitis",
            "secondary_diagnoses": [],
            "procedures": ["Laparoscopic appendectomy"],
            "medications": ["Inj Ceftriaxone 1g IV BD"],
            "admission_course": "Uneventful recovery.",
        }
    if "Assign ICD-10" in system:
        return {"codes": [{"icd_code": "K35.9", "confidence": 0.4}]}
    raise AssertionError(f"unscripted system prompt: {system!r}")


def _fake_retrieve(query, k):
    return [IcdEntry("K35.9", "Acute appendicitis, unspecified")]


def test_low_confidence_code_never_reaches_submitter():
    record = _record()
    deps = PipelineDeps(llm=_fake_llm, retrieve=_fake_retrieve, store={}, audit=lambda e: None)

    result = run_claim(record, deps)

    assert result["final_status"] == "needs_review"
    assert result["packaging"] == "needs_review"
    assert deps.store == {}
