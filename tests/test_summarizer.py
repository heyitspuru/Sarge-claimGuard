from claimguard.agents.summarizer import summarize
from claimguard.models import DischargeRecord, Insurance, Patient

FAKE_RESULT = {
    "primary_diagnosis": "Acute appendicitis",
    "secondary_diagnoses": [],
    "procedures": ["Laparoscopic appendectomy"],
    "medications": ["Inj Ceftriaxone 1g IV BD"],
    "admission_course": "Admitted with RIF pain; surgery day 1; uneventful recovery.",
}


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


def _fake_llm(result):
    def fn(prompt, *, system="", tier="fast", json_schema=None):
        return result
    return fn


def test_summarize_maps_source_fields():
    record = _record()
    summary = summarize(record, llm=_fake_llm(FAKE_RESULT))

    assert summary.record_id == record.record_id
    assert summary.primary_diagnosis == "Acute appendicitis"
    assert summary.procedures == ["Laparoscopic appendectomy"]
    assert summary.medications == ["Inj Ceftriaxone 1g IV BD"]
    assert summary.admission_course == "Admitted with RIF pain; surgery day 1; uneventful recovery."
    assert summary.source_fields == {
        "primary_diagnosis": "diagnosis_text",
        "secondary_diagnoses": "diagnosis_text",
        "procedures": "procedures",
        "medications": "medications",
        "admission_course": "clinical_notes",
    }


def test_summarize_ignores_extra_keys():
    record = _record()
    result_with_extra = FAKE_RESULT | {"invented_field": "should be ignored"}
    summary = summarize(record, llm=_fake_llm(result_with_extra))

    assert summary.primary_diagnosis == "Acute appendicitis"
    assert not hasattr(summary, "invented_field")


def test_summarize_defensive_missing_keys():
    """Test that summarize handles missing keys from non-schema-enforced LLM output."""
    record = _record()
    # Simulate Gemini not enforcing schema and missing secondary_diagnoses and medications
    incomplete_result = {
        "primary_diagnosis": "Acute appendicitis",
        "procedures": ["Laparoscopic appendectomy"],
        "admission_course": "Admitted with RIF pain; surgery day 1; uneventful recovery.",
    }
    summary = summarize(record, llm=_fake_llm(incomplete_result))

    # Should not raise KeyError; missing list fields default to []
    assert summary.record_id == "R0001"
    assert summary.primary_diagnosis == "Acute appendicitis"
    assert summary.secondary_diagnoses == []
    assert summary.medications == []
    assert summary.procedures == ["Laparoscopic appendectomy"]
    assert summary.admission_course == "Admitted with RIF pain; surgery day 1; uneventful recovery."
