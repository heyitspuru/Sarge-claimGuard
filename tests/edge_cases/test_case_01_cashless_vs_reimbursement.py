"""Edge case Sec9-1: cashless and reimbursement claims demand different document
sets, and each reaches "ready" packaging when its own set is complete.

# ponytail: remaining Sec9 cases land with their phases (2/3/4).
"""

from claimguard.agents.packager import package
from claimguard.models import CodedDiagnosis, DischargeRecord, DischargeSummary, Insurance, Patient
from claimguard.synth.templates import REQUIRED_DOCS


def _record(**kw):
    base = dict(
        record_id="R9001",
        patient=Patient(name="Test Patient", age=40, sex="F", abha_id="00-0000-0000-0000"),
        admission_date="2026-01-01", discharge_date="2026-01-03",
        claim_type="cashless", specialty="general_surgery",
        diagnosis_text="Acute appendicitis", procedures=["Laparoscopic appendectomy"],
        medications=["Inj Ceftriaxone 1g IV BD"], clinical_notes="Uneventful recovery.",
        documents=[],
        insurance=Insurance(insurer_id="INS1", plan_id="P1", policy_number="POL1",
                             sum_insured=500000, claimed_amount=80000),
    )
    return DischargeRecord(**(base | kw))


def _summary(record):
    return DischargeSummary(
        record_id=record.record_id, primary_diagnosis=record.diagnosis_text,
        secondary_diagnoses=[], procedures=record.procedures, medications=record.medications,
        admission_course=record.clinical_notes, source_fields={},
    )


def _code():
    return [CodedDiagnosis(icd_code="K35.9", description="Acute appendicitis, unspecified",
                            confidence=0.9, needs_review=False)]


def test_required_docs_differ_by_claim_type():
    cashless, reimbursement = REQUIRED_DOCS["cashless"], REQUIRED_DOCS["reimbursement"]
    assert set(cashless) != set(reimbursement)
    assert "preauth_form" in cashless and "preauth_form" not in reimbursement
    assert "payment_receipts" in reimbursement and "claim_form" in reimbursement


def test_cashless_ready_with_its_own_complete_docs():
    record = _record(claim_type="cashless", documents=list(REQUIRED_DOCS["cashless"]))
    result = package(record, _summary(record), _code())
    assert result.status == "ready"


def test_reimbursement_ready_with_its_own_complete_docs():
    record = _record(claim_type="reimbursement", documents=list(REQUIRED_DOCS["reimbursement"]))
    result = package(record, _summary(record), _code())
    assert result.status == "ready"
