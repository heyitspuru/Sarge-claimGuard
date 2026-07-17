from claimguard.agents.packager import package
from claimguard.models import CodedDiagnosis, DischargeRecord, DischargeSummary, Insurance, Patient


def _record(**kw):
    base = dict(
        record_id="R0001",
        patient=Patient(name="Asha Rao", age=34, sex="F", abha_id="12-3456-7890-0001"),
        admission_date="2026-07-01", discharge_date="2026-07-04",
        claim_type="cashless", specialty="general_surgery",
        diagnosis_text="Acute appendicitis", procedures=["Laparoscopic appendectomy"],
        medications=["Inj Ceftriaxone 1g IV BD"], clinical_notes="Uneventful recovery.",
        documents=["discharge_summary", "final_bill", "preauth_form", "id_proof"],
        insurance=Insurance(insurer_id="INS1", plan_id="P1", policy_number="POL123",
                            sum_insured=500000, claimed_amount=80000),
    )
    return DischargeRecord(**(base | kw))


def _summary(record):
    return DischargeSummary(
        record_id=record.record_id,
        primary_diagnosis=record.diagnosis_text,
        secondary_diagnoses=[],
        procedures=record.procedures,
        medications=record.medications,
        admission_course=record.clinical_notes,
        source_fields={},
    )


def _code(**kw):
    base = dict(icd_code="K35.9", description="Acute appendicitis", confidence=0.9, needs_review=False)
    return CodedDiagnosis(**(base | kw))


def test_missing_required_doc_rejected():
    record = _record(documents=["discharge_summary", "final_bill", "id_proof"])
    result = package(record, _summary(record), [_code()])
    assert result.status == "rejected"
    assert result.rejection_reasons == ["missing document: preauth_form"]


def test_empty_codes_rejected():
    record = _record()
    result = package(record, _summary(record), [])
    assert result.status == "rejected"
    assert result.rejection_reasons == ["no ICD codes assigned"]


def test_low_confidence_code_needs_review():
    record = _record()
    result = package(record, _summary(record), [_code(needs_review=True)])
    assert result.status == "needs_review"
    assert result.rejection_reasons == ["low-confidence code: K35.9"]
    assert result.fhir_claim is None


def test_happy_path_ready():
    record = _record()
    result = package(record, _summary(record), [_code()])
    assert result.status == "ready"
    assert result.fhir_claim["resourceType"] == "Claim"
    codes = [d["diagnosisCodeableConcept"]["coding"][0]["code"] for d in result.fhir_claim["diagnosis"]]
    assert "K35.9" in codes
