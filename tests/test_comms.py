"""Phase 4 exit criteria: trigger moments fire correctly, and the copy is human-safe."""

import pytest

from claimguard.comms import EVENTS, LANGUAGES, build_message, patient_status, plan_notifications
from claimguard.comms.messages import unsafe_terms
from claimguard.compliance_radar import radar
from claimguard.compliance_radar.radar import PREBREACH_MIN
from claimguard.models import Journey, RadarStage


def _journey(record_id="R0001", submit_at=90, claim_type="cashless"):
    """Journey with submission at a chosen minute, so trigger timing is exact."""
    stages = [
        RadarStage(stage="order", at_minutes=0),
        RadarStage(stage="summary", at_minutes=submit_at // 4),
        RadarStage(stage="code", at_minutes=submit_at // 2),
        RadarStage(stage="package", at_minutes=submit_at * 3 // 4),
        RadarStage(stage="submit", at_minutes=submit_at),
        RadarStage(stage="decision", at_minutes=submit_at + 60),
    ]
    return Journey(record_id=record_id, claim_type=claim_type, stages=stages)


# --- copy safety (the hard rule from CLAUDE.md) ---


@pytest.mark.parametrize("event", sorted(EVENTS))
@pytest.mark.parametrize("language", LANGUAGES)
def test_every_template_is_human_safe(event, language):
    text = EVENTS[event][language]
    assert unsafe_terms(text, language) == [], (
        f"{event}/{language} uses alarming language: {unsafe_terms(text, language)}"
    )


def test_claim_queried_copy_is_reassuring_not_alarming():
    """Snapshot of the copy the spec singles out — routine, handled, no action needed."""
    text = build_message("R0001", "claim_queried", "en", 120).text
    assert unsafe_terms(text) == []
    low = text.lower()
    assert "routine" in low                      # framed as normal, not as a setback
    assert "hospital team" in low                 # someone is already on it
    assert "nothing is needed from you" in low    # patient is not handed a task
    assert "as soon as there is news" in low      # the loop gets closed


def test_bad_news_always_arrives_with_a_next_step():
    for event in ("claim_queried", "claim_partial", "claim_rejected"):
        text = build_message("R0001", event, "en", 100).text.lower()
        assert "hospital team" in text, f"{event} leaves the patient without an owner"
        assert unsafe_terms(text) == []


def test_rejection_is_honest_but_not_final_sounding():
    text = build_message("R0001", "claim_rejected", "en", 100).text
    assert "not covered this claim under your policy" in text  # honest about the outcome
    assert "reconsider" in text.lower()                        # a door is still open
    assert "on your own" in text.lower()                       # patient is not alone
    assert unsafe_terms(text) == []


# --- trigger moments ---


def test_pharmacy_trigger_fires_at_order_not_approval():
    j = _journey(submit_at=90)
    msgs = plan_notifications(j, radar.analyze(j), outcome="approved")
    pharmacy = [m for m in msgs if m.event == "pharmacy_ready"]
    assert len(pharmacy) == 1
    assert pharmacy[0].at_minutes == 0, "pharmacy readiness must not wait on the insurer"
    assert pharmacy[0].at_minutes < min(
        m.at_minutes for m in msgs if m.event in ("claim_submitted", "claim_approved")
    )


def test_sla_alert_fires_at_prebreach_mark_when_submission_is_late():
    j = _journey(submit_at=150)  # past the 120-min pre-breach mark
    msgs = plan_notifications(j, radar.analyze(j))
    alerts = [m for m in msgs if m.event == "sla_prebreach"]
    assert len(alerts) == 1
    assert alerts[0].at_minutes == PREBREACH_MIN, "an early warning delivered late is not a warning"


def test_no_sla_alert_on_a_healthy_journey():
    j = _journey(submit_at=90)  # comfortably inside the SLA
    msgs = plan_notifications(j, radar.analyze(j))
    assert [m for m in msgs if m.event == "sla_prebreach"] == []


def test_messages_are_ordered_and_outcome_lands_last():
    j = _journey(submit_at=150)
    msgs = plan_notifications(j, radar.analyze(j), outcome="rejected")
    assert [m.at_minutes for m in msgs] == sorted(m.at_minutes for m in msgs)
    assert [m.event for m in msgs] == [
        "pharmacy_ready", "sla_prebreach", "claim_submitted", "claim_rejected",
    ]


def test_unknown_outcome_is_rejected_rather_than_silently_dropped():
    j = _journey()
    with pytest.raises(KeyError):
        plan_notifications(j, radar.analyze(j), outcome="exploded")


# --- multilingual delivery (§9-8 regional language) ---


@pytest.mark.parametrize("language", LANGUAGES)
def test_full_journey_delivers_updates_in_each_language(language):
    j = _journey(submit_at=150)
    msgs = plan_notifications(j, radar.analyze(j), language=language, outcome="partial")
    assert len(msgs) == 4
    assert {m.language for m in msgs} == {language}
    for m in msgs:
        assert m.text.strip()
        assert unsafe_terms(m.text, language) == []
    if language != "en":
        english = plan_notifications(j, radar.analyze(j), outcome="partial")
        assert [m.text for m in msgs] != [m.text for m in english], "not actually translated"


def test_unknown_language_degrades_to_english_never_to_blank():
    msg = build_message("R0001", "claim_queried", "kl", 10)
    assert msg.language == "en"
    assert msg.text == EVENTS["claim_queried"]["en"]


# --- patient view ---


def test_patient_view_reports_current_stage_and_eta():
    j = _journey(submit_at=120)
    report = radar.analyze(j)
    # mid-claim: coding done at 60, packaging next at 90
    status = patient_status(j, report, now_minutes=60)
    assert status.stage == "code"
    assert status.eta_min == 30
    assert "insurer" in status.happening.lower()
    assert status.elapsed_min == 60


def test_patient_view_after_decision_shows_outcome_copy_and_no_eta():
    j = _journey(submit_at=120)
    status = patient_status(j, radar.analyze(j), outcome="queried")
    assert status.stage == "decision"
    assert status.eta_min is None
    assert "routine" in status.next_step.lower()  # outcome copy replaces the generic line
    assert unsafe_terms(status.next_step) == []


def test_patient_view_never_leaks_pipeline_jargon():
    """Internal stage names mean nothing to a patient and must not surface."""
    j = _journey(submit_at=120)
    for lang in LANGUAGES:
        for now in (0, 30, 60, 90, 120, 180):
            s = patient_status(j, radar.analyze(j), language=lang, now_minutes=now)
            blob = f"{s.happening} {s.next_step}".lower()
            for jargon in ("fhir", "icd", "packag", "payload", "submit(", "pipeline", "agent"):
                assert jargon not in blob, f"{jargon!r} leaked at {now}m/{lang}"
