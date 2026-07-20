"""§9-4 — death in hospital → separate expedited/compassionate workflow.

This is primarily a **communications** case, and the most sensitive copy in the project.
Every message in the standard catalog addresses the patient directly and talks about
their discharge medicines and their claim. Sending any of it to a bereaved family would
be a serious harm, so the compassionate path REPLACES the schedule rather than filtering
it — there is no arrangement of the normal templates that is safe here.

CLAUDE.md makes "a patient-facing message that states bad news in an alarming rather
than human-safe way" a test failure. This is the sharpest instance of that rule.
"""

import pytest

from claimguard.comms import LANGUAGES, plan_notifications
from claimguard.comms.messages import COMPASSIONATE_EVENTS, EVENTS, build_message, unsafe_terms
from claimguard.compliance_radar import radar
from claimguard.models import DischargeRecord, Insurance, Journey, Patient, RadarStage

# Phrases from the discharge/claim catalogs whose arrival after a death would be
# actively harmful. Reassurance like "nothing is needed from you" is deliberately NOT
# here — it is appropriate in bereavement copy and appears there on purpose.
_HARMFUL_AFTER_DEATH = (
    "discharge medicines", "ready to collect", "when they are ready",
    "your claim has been sent", "min to submit",
)


def _record(disposition="deceased"):
    return DischargeRecord(
        record_id="R4001",
        patient=Patient(name="Test Patient", age=78, sex="M", abha_id="91-0000-0000-4001"),
        admission_date="2026-02-01", discharge_date="2026-02-09",
        claim_type="cashless", specialty="critical_care",
        diagnosis_text="Septic shock", procedures=["Mechanical ventilation"],
        medications=["Inj Noradrenaline"], clinical_notes="Deteriorated despite maximal support.",
        documents=["discharge_summary", "final_bill", "preauth_form", "id_proof"],
        insurance=Insurance(insurer_id="INS1", plan_id="P1", policy_number="POL-4001",
                            sum_insured=500000, claimed_amount=340000),
        disposition=disposition,
    )


def _journey(record_id="R4001"):
    return Journey(
        record_id=record_id, claim_type="cashless",
        stages=[
            RadarStage(stage="order", at_minutes=0),
            RadarStage(stage="summary", at_minutes=40),
            RadarStage(stage="code", at_minutes=70),
            RadarStage(stage="package", at_minutes=110),
            RadarStage(stage="submit", at_minutes=150),
            RadarStage(stage="decision", at_minutes=260),
        ],
    )


def test_disposition_defaults_to_discharged_so_existing_records_are_unaffected():
    assert _record(disposition="discharged").disposition == "discharged"
    assert DischargeRecord.model_validate(
        _record().model_dump() | {"disposition": "discharged"}).disposition == "discharged"


def test_no_standard_patient_message_is_sent_after_a_death():
    j = _journey()
    msgs = plan_notifications(j, radar.analyze(j), disposition="deceased", outcome="approved")

    sent = {m.event for m in msgs}
    assert sent.isdisjoint(set(EVENTS)), f"standard patient copy leaked to a family: {sent}"
    assert sent <= set(COMPASSIONATE_EVENTS)


def test_pharmacy_message_is_never_sent_after_a_death():
    """The single most harmful possible message: 'your medicines are ready to collect'."""
    j = _journey()
    msgs = plan_notifications(j, radar.analyze(j), disposition="deceased")

    assert "pharmacy_ready" not in {m.event for m in msgs}
    for m in msgs:
        for phrase in _HARMFUL_AFTER_DEATH:
            assert phrase not in m.text.lower(), f"harmful phrasing after death: {phrase!r}"


def test_condolence_comes_first_and_the_claim_is_not_the_opening_subject():
    j = _journey()
    msgs = plan_notifications(j, radar.analyze(j), disposition="deceased", outcome="rejected")

    assert msgs[0].event == "condolence_hold"
    assert msgs[0].at_minutes == 0
    first = msgs[0].text.lower()
    assert "sorry for your loss" in first
    assert first.index("sorry") < first.index("insurance"), "condolence must precede logistics"


def test_a_denial_after_death_is_never_delivered_as_a_denial_to_the_family():
    """Bad claim news must not be the message a bereaved family receives."""
    j = _journey()
    msgs = plan_notifications(j, radar.analyze(j), disposition="deceased", outcome="rejected")

    blob = " ".join(m.text.lower() for m in msgs)
    assert "not covered" not in blob
    assert "claim_rejected" not in {m.event for m in msgs}
    # what they get instead: the hospital has handled it and will help
    assert "hospital team" in blob


@pytest.mark.parametrize("language", LANGUAGES)
def test_compassionate_copy_exists_and_is_safe_in_every_language(language):
    for event in COMPASSIONATE_EVENTS:
        text = COMPASSIONATE_EVENTS[event][language]
        assert text.strip()
        assert unsafe_terms(text, language, context="condolence") == []


def test_condolence_register_permits_apology_but_claim_register_does_not():
    """The same word, opposite verdicts — which is why the contract takes a context."""
    apology = "We are so sorry for your loss."
    assert unsafe_terms(apology, "en", context="condolence") == []
    assert unsafe_terms(apology, "en", context="claim") == ["sorry"]


def test_condolence_context_does_not_unblock_genuinely_alarming_words():
    """Widening the register must not become a hole in the copy contract."""
    assert unsafe_terms("Your claim was rejected.", "en", context="condolence") == ["rejected"]


@pytest.mark.parametrize("language", LANGUAGES)
def test_compassionate_path_delivers_in_the_family_s_language(language):
    j = _journey()
    msgs = plan_notifications(j, radar.analyze(j), language=language, disposition="deceased",
                              outcome="partial")
    assert {m.language for m in msgs} == {language}
    assert all(m.text.strip() for m in msgs)


def test_build_message_resolves_compassionate_events():
    msg = build_message("R4001", "condolence_hold", "en", 0)
    assert msg.event == "condolence_hold"
    assert "sorry for your loss" in msg.text.lower()


def test_discharged_patients_keep_the_normal_schedule():
    """The compassionate path must not leak into ordinary claims."""
    j = _journey()
    msgs = plan_notifications(j, radar.analyze(j), disposition="discharged", outcome="approved")

    events = {m.event for m in msgs}
    assert "pharmacy_ready" in events
    assert events.isdisjoint(set(COMPASSIONATE_EVENTS))
