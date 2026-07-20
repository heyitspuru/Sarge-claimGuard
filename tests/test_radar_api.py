from fastapi.testclient import TestClient

from claimguard.api import app

client = TestClient(app)


def test_journeys_list_labeled_synthetic():
    r = client.get("/radar/journeys")
    assert r.status_code == 200
    body = r.json()
    assert body["synthetic"] is True
    assert body["baseline"]["discharge_sla_min"] == 180
    assert len(body["journeys"]) >= 10
    # sorted worst-first
    delays = [j["pre_submission_delay_min"] for j in body["journeys"]]
    assert delays == sorted(delays, reverse=True)
    assert all(j["synthetic"] is True for j in body["journeys"])


def test_journey_detail_has_stages_and_report():
    rid = client.get("/radar/journeys").json()["journeys"][0]["record_id"]
    r = client.get(f"/radar/journey/{rid}")
    assert r.status_code == 200
    body = r.json()
    assert body["synthetic"] is True
    assert [s["stage"] for s in body["journey"]["stages"]][0] == "order"
    assert body["report"]["record_id"] == rid
    assert body["report"]["slowest_stage"] in body["report"]["stage_gaps"]


def test_unknown_journey_404s():
    assert client.get("/radar/journey/NOPE-0000").status_code == 404
