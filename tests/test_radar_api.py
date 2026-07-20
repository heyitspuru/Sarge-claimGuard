"""Compliance Radar API. Staff-only — see tests/test_auth_api.py for the access
boundary itself; these cover the payload once you are past it."""

from fastapi.testclient import TestClient

from claimguard.api import app


def test_journeys_list_labeled_synthetic(staff_client):
    r = staff_client.get("/radar/journeys")
    assert r.status_code == 200
    body = r.json()
    assert body["synthetic"] is True
    assert body["baseline"]["discharge_sla_min"] == 180
    assert len(body["journeys"]) >= 10
    # sorted worst-first
    delays = [j["pre_submission_delay_min"] for j in body["journeys"]]
    assert delays == sorted(delays, reverse=True)
    assert all(j["synthetic"] is True for j in body["journeys"])


def test_journey_detail_has_stages_and_report(staff_client):
    rid = staff_client.get("/radar/journeys").json()["journeys"][0]["record_id"]
    r = staff_client.get(f"/radar/journey/{rid}")
    assert r.status_code == 200
    body = r.json()
    assert body["synthetic"] is True
    assert [s["stage"] for s in body["journey"]["stages"]][0] == "order"
    assert body["report"]["record_id"] == rid
    assert body["report"]["slowest_stage"] in body["report"]["stage_gaps"]


def test_unknown_journey_404s(staff_client):
    assert staff_client.get("/radar/journey/NOPE-0000").status_code == 404


def test_radar_is_not_reachable_without_a_staff_session():
    """The journey list is the record enumeration — it must never be public."""
    with TestClient(app) as anon:
        assert anon.get("/radar/journeys").status_code == 401
        assert anon.get("/radar/journey/R0001").status_code == 401
