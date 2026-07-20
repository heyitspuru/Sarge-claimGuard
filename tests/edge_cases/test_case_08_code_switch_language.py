"""§9-8 — code-switched / regional language in inputs.

Two halves to this case:
  (a) INPUT: clinical free text arrives code-switched (Hinglish/Tanglish, Devanagari
      or Tamil script mixed into English notes). The pipeline must still produce a
      summary and codes rather than choking on the script.
  (b) OUTPUT: the patient is answered in THEIR language, not the language the
      hospital happened to type in.
"""

import pytest

from claimguard.agents.summarizer import summarize
from claimguard.comms import LANGUAGES, patient_status, plan_notifications
from claimguard.comms.messages import unsafe_terms
from claimguard.compliance_radar import radar
from claimguard.models import DischargeRecord, Insurance, Journey, Patient, RadarStage

CODE_SWITCHED_NOTES = (
    "Patient ko 3 din se tez bukhar tha, cough bhi tha. "
    "Admitted with febrile illness; दवा शुरू की गई and IV fluids given. "
    "Blood culture negative. Patient ab stable hai, discharge on oral antibiotics."
)


def _record(notes=CODE_SWITCHED_NOTES) -> DischargeRecord:
    return DischargeRecord(
        record_id="R9008",
        patient=Patient(name="Test Patient", age=41, sex="F", abha_id="91-0000-0000-0008"),
        admission_date="2026-03-01",
        discharge_date="2026-03-04",
        claim_type="cashless",
        specialty="internal_medicine",
        diagnosis_text="Febrile illness, resolved",
        procedures=["IV fluid therapy"],
        medications=["Paracetamol", "Amoxicillin"],
        clinical_notes=notes,
        documents=["discharge_summary", "id_proof", "policy_copy"],
        insurance=Insurance(
            insurer_id="INS001", plan_id="PLAN_A",
            policy_number="POL-9008", sum_insured=500000, claimed_amount=42000,
        ),
    )


def _journey(record_id="R9008", submit_at=150) -> Journey:
    return Journey(
        record_id=record_id,
        claim_type="cashless",
        stages=[
            RadarStage(stage="order", at_minutes=0),
            RadarStage(stage="summary", at_minutes=submit_at // 3),
            RadarStage(stage="code", at_minutes=submit_at // 2),
            RadarStage(stage="package", at_minutes=submit_at * 3 // 4),
            RadarStage(stage="submit", at_minutes=submit_at),
            RadarStage(stage="decision", at_minutes=submit_at + 45),
        ],
    )


def _fake_llm(result):
    def fn(prompt, *, system="", tier="fast", json_schema=None):
        return result
    return fn


def test_code_switched_notes_do_not_break_summarization():
    """Mixed-script input must round-trip through the pipeline, not raise."""
    llm = _fake_llm({
        "primary_diagnosis": "Febrile illness",
        "secondary_diagnoses": [],
        "procedures": ["IV fluid therapy"],
        "medications": ["Paracetamol", "Amoxicillin"],
        "admission_course": "Admitted with fever; treated with IV fluids; stable at discharge.",
    })
    summary = summarize(_record(), llm=llm)
    assert summary.record_id == "R9008"
    assert summary.primary_diagnosis.strip()
    # source_fields must still trace back to the record (grounding, not translation)
    assert summary.source_fields


def test_non_latin_script_survives_intact():
    """Devanagari/Tamil in the record must not be mangled or stripped en route."""
    rec = _record("Fever x3 days. रोगी को बुखार था। காய்ச்சல் இருந்தது. Now stable.")
    assert "रोगी" in rec.clinical_notes
    assert "காய்ச்சல்" in rec.clinical_notes
    assert rec.model_dump()["clinical_notes"] == rec.clinical_notes


@pytest.mark.parametrize("language", LANGUAGES)
def test_patient_is_answered_in_their_language_not_the_chart_language(language):
    """The notes are Hinglish; what the patient receives follows THEIR preference."""
    j = _journey()
    report = radar.analyze(j)
    msgs = plan_notifications(j, report, language=language, outcome="queried")

    assert {m.language for m in msgs} == {language}
    for m in msgs:
        assert m.text.strip()
        assert unsafe_terms(m.text, language) == [], "regional copy must be as safe as English"

    status = patient_status(j, report, language=language, outcome="queried")
    assert status.language == language
    assert status.happening.strip() and status.next_step.strip()


def test_regional_copy_is_actually_translated_not_english_passthrough():
    j = _journey()
    report = radar.analyze(j)
    texts = {
        lang: [m.text for m in plan_notifications(j, report, language=lang, outcome="rejected")]
        for lang in LANGUAGES
    }
    assert texts["hi"] != texts["en"]
    assert texts["ta"] != texts["en"]
    assert texts["hi"] != texts["ta"]
    # spot-check the scripts really are the target scripts
    assert any("ऀ" <= ch <= "ॿ" for ch in " ".join(texts["hi"])), "no Devanagari"
    assert any("஀" <= ch <= "௿" for ch in " ".join(texts["ta"])), "no Tamil"
