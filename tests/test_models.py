from claimguard.models import ClaimPackage, DischargeRecord, Insurance, Patient


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


def test_record_roundtrip_json():
    r = _record()
    assert DischargeRecord.model_validate_json(r.model_dump_json()) == r


def test_claim_type_validated():
    import pytest
    with pytest.raises(Exception):
        _record(claim_type="cash")


def test_package_defaults():
    p = ClaimPackage(record_id="R1", status="rejected", rejection_reasons=["missing preauth_form"])
    assert p.fhir_claim is None
