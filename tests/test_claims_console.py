"""The hospital console: a work queue and per-claim review, not just a dashboard.

The rule this exists to enforce: **a model-drafted appeal is never sent without a human
reading it.** Same reflex as "a low-confidence code never reaches submission
unreviewed" — an appeal is a formal communication to an insurer on a patient's behalf.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from claimguard import advocacy, appeals_store
from claimguard.api import app
from claimguard.models import AppealResult, Citation


@pytest.fixture(autouse=True)
def _isolate_appeal_store(tmp_path, monkeypatch):
    """Redirect only the drafts directory, so tests never write into data/appeals.

    Deliberately narrower than repointing data_dir: the golden corpus and policies must
    still be the real ones, or these tests would prove nothing about real records.
    """
    monkeypatch.setattr(appeals_store, "_dir", lambda: tmp_path / "appeals")
    yield


def _a_denied_record() -> str:
    for path in sorted(Path("data/golden").glob("*.json"))[:50]:
        rid = json.loads(path.read_text(encoding="utf-8"))["record"]["record_id"]
        if advocacy.outcome_for(rid) in ("partial", "rejected"):
            return rid
    pytest.skip("no denied record in the corpus")


def _an_approved_record() -> str:
    for path in sorted(Path("data/golden").glob("*.json"))[:50]:
        rid = json.loads(path.read_text(encoding="utf-8"))["record"]["record_id"]
        if advocacy.outcome_for(rid) == "approved":
            return rid
    pytest.skip("no approved record in the corpus")


def _fake_appeal(record_id: str) -> AppealResult:
    return AppealResult(
        scenario_id=f"AUTO-{record_id}", status="appeal",
        appeal_text="The sub-limit was over-applied.",
        citations=[Citation(clause_id="STAR-SEC1-C01", quoted_text="cover",
                            relevance="provides cover")],
        reasoning="grounded",
    )


# --- access -------------------------------------------------------------------


def test_console_is_staff_only():
    with TestClient(app) as anon:
        assert anon.get("/claims/queue").status_code == 401
        assert anon.get("/claims/R0001").status_code == 401
        assert anon.post("/claims/R0001/appeal").status_code == 401
        assert anon.post("/claims/R0001/appeal/review",
                         json={"state": "approved"}).status_code == 401


def test_a_patient_cannot_reach_the_console(patient_client):
    client, _ = patient_client
    assert client.get("/claims/queue").status_code == 403
    assert client.get("/claims/R0001").status_code == 403


# --- the queue ----------------------------------------------------------------


def test_queue_surfaces_only_claims_that_need_a_person(staff_client):
    rows = staff_client.get("/claims/queue").json()["queue"]
    assert rows, "nothing queued at all — the queue is not deriving work"
    for row in rows:
        needs_work = row["outcome"] in ("partial", "rejected")
        assert needs_work or row["breach_status"] == "breach", (
            f"{row['record_id']} is queued but neither denied nor breaching"
        )


def test_queue_puts_awaiting_review_before_everything_else(staff_client):
    """A drafted appeal sitting unread is the most time-sensitive thing here."""
    rid = _a_denied_record()
    appeals_store.save(rid, _fake_appeal(rid), drafted_by="test")

    rows = staff_client.get("/claims/queue").json()["queue"]
    actions = [r["action"] for r in rows]
    if "needs_review" in actions:
        assert actions.index("needs_review") == 0


def test_queue_marks_claims_with_no_grounded_appeal_distinctly(staff_client):
    """"We looked and there is no appeal" is a different state from "not looked at"."""
    rows = staff_client.get("/claims/queue").json()["queue"]
    actions = {r["action"] for r in rows}
    assert "no_appeal_available" in actions or "needs_draft" in actions


# --- claim detail -------------------------------------------------------------


def test_claim_detail_carries_decision_advocacy_and_consent(staff_client):
    rid = _a_denied_record()
    body = staff_client.get(f"/claims/{rid}").json()
    assert body["record_id"] == rid
    assert body["outcome"] in ("partial", "rejected")
    assert body["advocacy"]["cited_clause"]["clause_id"]
    assert body["consent_withdrawn"] is False
    assert body["appeal"] is None, "no draft should exist until someone asks for one"


def test_unknown_claim_404s(staff_client):
    assert staff_client.get("/claims/NOPE-0000").status_code == 404


# --- drafting -----------------------------------------------------------------


def test_cannot_draft_an_appeal_for_an_approved_claim(staff_client):
    rid = _an_approved_record()
    r = staff_client.post(f"/claims/{rid}/appeal")
    assert r.status_code == 400
    assert "nothing to appeal" in r.json()["detail"].lower()


def test_drafting_on_the_mock_provider_is_refused_not_faked(staff_client):
    """The mock returns an empty completion, which the grounding gate downgrades to
    `no_valid_appeal` — visually identical to the Negotiator examining a case and
    genuinely declining. Serving that as a refusal would undermine the one property
    this agent exists for, so it is refused outright instead."""
    rid = _a_denied_record()
    r = staff_client.post(f"/claims/{rid}/appeal")  # conftest pins LLM_PROVIDER=mock

    assert r.status_code == 400
    detail = r.json()["detail"].lower()
    assert "mock" in detail
    assert "honest refusal" in detail, "the message must explain WHY a fake refusal is bad"
    assert appeals_store.get(rid) is None, "a refused draft must not be stored"


def test_quota_exhaustion_reports_the_real_limit(staff_client, monkeypatch):
    """A 503 naming the actual ceiling beats a generic failure the user cannot act on."""
    from claimguard import appeal as appeal_module
    from claimguard.config import get_settings

    from claimguard import api as api_module
    from claimguard.llm import _mock_embed

    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()

    # The endpoint builds a PolicyRetriever (which embeds every clause) before it ever
    # reaches the handler. Left alone with provider=gemini that is a REAL network call —
    # the same trap that made tests/integration/test_pipeline.py hit the API at
    # collection time. Pin the embedder so this test stays offline.
    monkeypatch.setattr(api_module.llm, "embed", _mock_embed)

    def exhausted(*_args, **_kwargs):
        def handler(*_a, **_k):
            raise RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded")
        return handler

    monkeypatch.setattr(appeal_module, "make_appeal_handler", exhausted)
    try:
        r = staff_client.post(f"/claims/{_a_denied_record()}/appeal")
        assert r.status_code == 503
        assert "20" in r.json()["detail"], "the actual daily limit should be named"
    finally:
        get_settings.cache_clear()


def test_draft_lands_in_drafted_never_pre_approved(staff_client):
    """The whole point of the review gate is that drafting is not sending."""
    rid = _a_denied_record()
    payload = appeals_store.save(rid, _fake_appeal(rid), drafted_by="tester")
    assert payload["review_state"] == "drafted"
    assert payload["reviewed_by"] is None

    detail = staff_client.get(f"/claims/{rid}").json()
    assert detail["appeal"]["review_state"] == "drafted"


# --- human review ------------------------------------------------------------


def test_a_human_must_approve_before_an_appeal_is_sent(staff_client):
    rid = _a_denied_record()
    appeals_store.save(rid, _fake_appeal(rid), drafted_by="drafter")

    r = staff_client.post(f"/claims/{rid}/appeal/review",
                          json={"state": "approved", "note": "reads correctly"})
    assert r.status_code == 200
    body = r.json()
    assert body["review_state"] == "approved"
    assert body["reviewed_by"], "an approval with no reviewer is not a review"
    assert body["reviewed_at"]
    assert body["review_note"] == "reads correctly"


def test_a_reviewer_can_decline_a_draft(staff_client):
    rid = _a_denied_record()
    appeals_store.save(rid, _fake_appeal(rid), drafted_by="drafter")
    body = staff_client.post(f"/claims/{rid}/appeal/review",
                             json={"state": "declined",
                                   "note": "exclusion actually applies"}).json()
    assert body["review_state"] == "declined"
    assert body["review_note"] == "exclusion actually applies"


def test_review_requires_a_draft_to_review(staff_client):
    rid = _a_denied_record()
    assert staff_client.post(f"/claims/{rid}/appeal/review",
                             json={"state": "approved"}).status_code == 404


def test_invalid_review_state_is_refused(staff_client):
    rid = _a_denied_record()
    appeals_store.save(rid, _fake_appeal(rid), drafted_by="drafter")
    assert staff_client.post(f"/claims/{rid}/appeal/review",
                             json={"state": "sent"}).status_code == 400


def test_review_is_recorded_durably(staff_client):
    rid = _a_denied_record()
    appeals_store.save(rid, _fake_appeal(rid), drafted_by="drafter")
    staff_client.post(f"/claims/{rid}/appeal/review", json={"state": "approved"})

    reloaded = appeals_store.get(rid)
    assert reloaded["review_state"] == "approved"
    assert reloaded["reviewed_by"]


def test_store_rejects_a_nonsense_review_state():
    with pytest.raises(ValueError):
        appeals_store.review("R0001", "sent", reviewed_by="x")


def _a_refusal(record_id: str) -> AppealResult:
    """What the Negotiator stores when it examines a claim and declines to appeal."""
    return AppealResult(
        scenario_id=f"AUTO-{record_id}", status="no_valid_appeal",
        appeal_text="", citations=[],
        reasoning="the sub-limit the insurer applied genuinely sits in this policy",
    )


def test_a_refusal_cannot_be_approved_to_send(staff_client):
    """"Approved" means cleared to go to the insurer. On a refusal there is no letter —
    empty `appeal_text`, no citations — so approving it asserts an appeal is on its way
    when nothing exists. Terminal, not pending."""
    rid = _a_denied_record()
    appeals_store.save(rid, _a_refusal(rid), drafted_by="drafter")

    r = staff_client.post(f"/claims/{rid}/appeal/review", json={"state": "approved"})
    assert r.status_code == 400
    assert "no letter" in r.json()["detail"]
    assert appeals_store.get(rid)["review_state"] == "drafted", "must stay untouched"


def test_a_refusal_cannot_be_declined_either(staff_client):
    rid = _a_denied_record()
    appeals_store.save(rid, _a_refusal(rid), drafted_by="drafter")
    assert staff_client.post(f"/claims/{rid}/appeal/review",
                             json={"state": "declined"}).status_code == 400
