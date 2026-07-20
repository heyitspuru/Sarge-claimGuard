"""Edge case Sec9-5: a misnamed document ("final_bil" instead of "final_bill")
is caught pre-submission. The claim is rejected, with a reason naming the
actual missing document rather than silently accepting the typo.
"""

from claimguard.agents.packager import package
from claimguard.models import CodedDiagnosis, DischargeRecord, DischargeSummary, Insurance, Patient


def _record(**kw):
    base = dict(
        record_id="R9002",
        patient=Patient(name="Test Patient", age=40, sex="F", abha_id="00-0000-0000-0000"),
        admission_date="2026-01-01", discharge_date="2026-01-03",
        claim_type="cashless", specialty="general_surgery",
        diagnosis_text="Acute appendicitis", procedures=["Laparoscopic appendectomy"],
        medications=["Inj Ceftriaxone 1g IV BD"], clinical_notes="Uneventful recovery.",
        documents=["discharge_summary", "final_bil", "preauth_form", "id_proof"],
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


def test_misnamed_document_caught_pre_submission():
    record = _record()
    result = package(record, _summary(record), _code())

    assert result.status == "rejected"
    assert any("final_bill" in reason for reason in result.rejection_reasons)
    assert result.fhir_claim is None
