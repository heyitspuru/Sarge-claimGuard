"""The end-to-end demo walkthrough.

The demo is the artifact most people will judge this project by, so the thing worth
testing is not that it prints prettily — it is that it cannot make a claim the rest of
the system would not stand behind.
"""

import pytest

from claimguard import demo


@pytest.fixture
def walkthrough(capsys):
    def run(record_id=None, language="en"):
        assert demo.run(record_id, language=language) == 0
        return capsys.readouterr().out

    return run


def test_the_walkthrough_covers_every_stage(walkthrough):
    out = walkthrough("R0011")
    for section in ("THE AGENTS", "THE SETTLEMENT", "THE RECORD TIMELINE",
                    "THE ADVOCACY", "WHAT THE PATIENT SEES", "WHAT THE HOSPITAL SEES"):
        assert section in out, f"the demo no longer shows {section}"


def test_it_never_presents_a_mock_completion_as_a_refusal(walkthrough):
    """conftest pins LLM_PROVIDER=mock. The mock returns an empty completion that the
    grounding gate downgrades to `no_valid_appeal` — visually identical to the Negotiator
    genuinely declining. Showing that in a demo would fake the one property the project
    exists to demonstrate, so no appeal handler is wired on the mock at all."""
    out = walkthrough("R0011")
    assert "running on the mock provider" in out or "STORED DRAFT" in out
    assert "LIVE DRAFT" not in out, "a live draft cannot exist on the mock provider"


def test_it_labels_mock_codes_as_meaningless(walkthrough):
    """On the mock the coder emits a deterministic stub unrelated to the diagnosis.
    Unlabelled, a viewer reads 'cataract -> K35.2' as the system being broken."""
    out = walkthrough("R0011")
    assert "MOCK PROVIDER" in out
    assert "meaningless as accuracy" in out


def test_the_settlement_shows_what_the_patient_actually_loses(walkthrough):
    out = walkthrough("R0011")
    assert "SHORTFALL" in out, "an approved-vs-claimed gap is the patient's out-of-pocket"
    assert "STAR-SEC1-C03" in out, "the denial must name the real clause it rests on"


def test_the_close_states_the_limitations(walkthrough):
    """The demo ends on what it is not. Losing this would make it a sales pitch."""
    out = walkthrough("R0011")
    for caveat in ("synthetic", "UNADJUDICATED", "PRODUCTION_READINESS"):
        assert caveat in out


def test_it_picks_a_denied_record_when_none_is_named():
    """An approved claim gives the Negotiator nothing to do — a dull demo of the one
    thing worth showing."""
    from claimguard import advocacy

    rid = demo.pick_record()
    assert rid is not None
    assert advocacy.outcome_for(rid) in ("partial", "rejected")


@pytest.mark.parametrize("language", ["en", "hi", "ta"])
def test_the_patient_section_runs_in_every_language(walkthrough, language):
    assert "WHAT THE PATIENT SEES" in walkthrough("R0011", language)


def test_an_unknown_record_fails_cleanly_rather_than_traceback(capsys):
    assert demo.run("NOPE-0000") == 1
    assert "not in the golden corpus" in capsys.readouterr().out
