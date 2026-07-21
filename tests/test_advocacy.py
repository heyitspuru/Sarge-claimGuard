"""The advocacy track: what the patient is told about their appeal, and when.

Encodes the product decision — resolved-then-reported with a visible seam. A denial is
never narrated as bad news the moment it lands, but the patient is never left in silence
either: a lead immediately, the full story (naming the real clause) once filed.
"""

import json
from pathlib import Path

import pytest

from claimguard import advocacy
from claimguard.comms import ADVOCACY_EVENTS, LANGUAGES, advocacy_messages
from claimguard.comms.messages import unsafe_terms
from claimguard.coverage import clause_ids, load_policies

POLICIES = load_policies(Path("data/policies"))
CORPUS_IDS = clause_ids(POLICIES)


def _states_by_kind() -> dict[str, str]:
    """One record_id per advocacy state, drawn from the real corpus."""
    found: dict[str, str] = {}
    for path in sorted(Path("data/golden").glob("*.json"))[:50]:
        rid = json.loads(path.read_text(encoding="utf-8"))["record"]["record_id"]
        found.setdefault(advocacy.advocacy_state(rid)["state"], rid)
    return found


STATES = _states_by_kind()


def _require(state: str) -> str:
    if state not in STATES:
        pytest.skip(f"no record in the corpus produces state {state}")
    return STATES[state]


# --- state derivation ---------------------------------------------------------


def test_all_three_states_occur_in_the_corpus():
    """A demo that only ever shows the refusal would misrepresent the product."""
    assert {"none", "filed", "no_valid_appeal"} <= set(STATES)


def test_approved_claim_has_nothing_to_advocate():
    state = advocacy.advocacy_state(_require("none"))
    assert state["state"] == "none"
    assert state["cited_clause"] is None


def test_a_limit_denial_produces_a_grounded_appeal():
    state = advocacy.advocacy_state(_require("filed"))
    assert state["state"] == "filed"
    assert state["cited_clause"]["clause_type"] == "sub_limit"
    assert state["supporting_clause"]["clause_type"] == "coverage"


def test_an_exclusion_denial_produces_an_honest_refusal():
    """When the exclusion genuinely applies, claiming to fight it would be worse than
    not fighting."""
    state = advocacy.advocacy_state(_require("no_valid_appeal"))
    assert state["state"] == "no_valid_appeal"
    assert state["supporting_clause"] is None
    assert state["cited_clause"]["clause_type"] in ("exclusion", "waiting_period")


def test_every_clause_shown_to_a_patient_is_real():
    """Same rule as the Negotiator: a citation the corpus cannot resolve is a defect."""
    for path in sorted(Path("data/golden").glob("*.json"))[:50]:
        rid = json.loads(path.read_text(encoding="utf-8"))["record"]["record_id"]
        state = advocacy.advocacy_state(rid)
        for key in ("cited_clause", "supporting_clause"):
            clause = state[key]
            if clause is not None:
                assert clause["clause_id"] in CORPUS_IDS, f"{rid}: fabricated {key}"


def test_clause_text_is_quoted_verbatim_never_paraphrased():
    """A 'simplified' policy term is a legal statement we are not qualified to make."""
    by_id = {c["clause_id"]: c["text"] for p in POLICIES for c in p["clauses"]}
    state = advocacy.advocacy_state(_require("filed"))
    for key in ("cited_clause", "supporting_clause"):
        clause = state[key]
        assert clause["text"] == by_id[clause["clause_id"]]


def test_state_is_deterministic():
    rid = _require("filed")
    assert advocacy.advocacy_state(rid) == advocacy.advocacy_state(rid)


def test_outcome_matches_the_real_submitter():
    """The patient view and the pipeline must never disagree about what happened."""
    from claimguard.agents.submitter import submit
    from claimguard.models import ClaimPackage

    for rid in STATES.values():
        expected = submit(ClaimPackage(record_id=rid, status="ready"), {}).outcome
        assert advocacy.outcome_for(rid) == expected


def test_unknown_record_degrades_to_nothing_rather_than_guessing():
    assert advocacy.advocacy_state("NOPE-9999")["state"] == "none"


# --- the message sequence -----------------------------------------------------


def test_the_lead_arrives_with_the_decision_and_the_story_comes_later():
    """The gap between the two is the design: a window of 'someone is on this' rather
    than either silence or bad news."""
    msgs = advocacy_messages("R0011", decision_at=300, state="filed", filed_after_min=90)

    assert [m.event for m in msgs] == ["advocacy_reviewing", "advocacy_filed"]
    assert msgs[0].at_minutes == 300, "the lead must land with the decision, not after"
    assert msgs[1].at_minutes == 390, "the full story comes after the review window"


def test_the_refusal_is_also_delivered_not_silently_dropped():
    msgs = advocacy_messages("R0000", decision_at=300, state="no_valid_appeal")
    assert [m.event for m in msgs] == ["advocacy_reviewing", "advocacy_no_valid_appeal"]


def test_an_approved_claim_gets_no_advocacy_messages():
    assert advocacy_messages("R0002", decision_at=300, state="none") == []


def test_the_lead_never_states_the_outcome():
    """It is sent before we know how it goes — it must not imply either direction."""
    text = ADVOCACY_EVENTS["advocacy_reviewing"]["en"].lower()
    for leak in ("denied", "rejected", "not covered", "refused", "won", "success"):
        assert leak not in text


# --- copy safety --------------------------------------------------------------


@pytest.mark.parametrize("event", sorted(ADVOCACY_EVENTS))
@pytest.mark.parametrize("language", LANGUAGES)
def test_advocacy_copy_is_human_safe(event, language):
    text = ADVOCACY_EVENTS[event][language]
    assert text.strip()
    assert unsafe_terms(text, language) == []


def test_advocacy_copy_always_names_who_is_acting():
    """A patient must never be left wondering whether anyone is actually doing this."""
    for event in ADVOCACY_EVENTS:
        text = ADVOCACY_EVENTS[event]["en"].lower()
        assert "we " in text or "your hospital team" in text


def test_the_refusal_still_offers_a_next_step():
    text = ADVOCACY_EVENTS["advocacy_no_valid_appeal"]["en"].lower()
    assert "hospital team" in text
    assert "options" in text
    assert "alone" in text, "an honest no must not also be an abandonment"


@pytest.mark.parametrize("language", LANGUAGES)
def test_advocacy_track_is_delivered_in_the_patients_language(language):
    msgs = advocacy_messages("R0011", 300, "filed", language=language)
    assert {m.language for m in msgs} == {language}
    assert all(m.text.strip() for m in msgs)


# --- the Negotiator's verdict outranks the prediction -------------------------


def _stub_draft(status: str) -> dict:
    return {"record_id": "X", "appeal": {"scenario_id": "S", "status": status,
                                          "appeal_text": "", "citations": [],
                                          "reasoning": "r"},
            "review_state": "drafted", "drafted_by": "t", "drafted_at": "now",
            "reviewed_by": None, "reviewed_at": None, "review_note": ""}


def test_a_real_refusal_overrides_a_predicted_filing(monkeypatch):
    """The clause-type prediction says "filed"; the Negotiator actually declined.

    Found by the end-to-end demo, not by a test: the patient was being sent "we have
    written back to your insurer on your behalf" for a claim the Negotiator had examined
    and refused to appeal. A message describing action taken must come from the action.
    """
    rid = _require("filed")
    assert advocacy.advocacy_state(rid)["state"] == "filed"

    monkeypatch.setattr(advocacy.appeals_store, "get",
                        lambda _rid: _stub_draft("no_valid_appeal"))
    state = advocacy.advocacy_state(rid)
    assert state["state"] == "no_valid_appeal"
    assert state["supporting_clause"] is None, (
        "a refusal has no clause to stand on; leaving one implies an argument we did "
        "not make")


def test_the_patient_is_not_told_an_appeal_was_filed_when_it_was_not(monkeypatch):
    """The end-to-end consequence, asserted on the copy the patient actually receives."""
    rid = _require("filed")
    monkeypatch.setattr(advocacy.appeals_store, "get",
                        lambda _rid: _stub_draft("no_valid_appeal"))
    state = advocacy.advocacy_state(rid)
    texts = " ".join(m.text for m in advocacy_messages(
        rid, 100, state["state"], language="en",
        filed_after_min=state["filed_after_min"]))
    for claim in ("written back to your insurer", "asked them to look again"):
        assert claim not in texts, f"patient told {claim!r} but no appeal was filed"


def test_a_real_appeal_confirms_the_filing(monkeypatch):
    """The override runs both ways — a genuine draft must not be downgraded."""
    rid = _require("filed")
    monkeypatch.setattr(advocacy.appeals_store, "get", lambda _rid: _stub_draft("appeal"))
    assert advocacy.advocacy_state(rid)["state"] == "filed"
