"""Patient view API. The record always comes from the session, never from the URL —
see tests/test_auth_api.py for why that shape was chosen."""

from fastapi.testclient import TestClient

from claimguard.api import app


def test_patient_view_returns_plain_language_status(patient_client):
    client, record_id = patient_client
    r = client.get("/patient/me")
    assert r.status_code == 200
    body = r.json()
    assert body["synthetic"] is True
    status = body["status"]
    assert status["record_id"] == record_id
    assert status["happening"].strip()
    assert status["next_step"].strip()
    assert status["sla_min"] == 180
    assert status["messages"], "a journey should always have sent at least the pharmacy message"
    assert status["messages"][0]["event"] == "pharmacy_ready"


def test_patient_view_honours_language(patient_client):
    client, _ = patient_client
    en = client.get("/patient/me?lang=en").json()["status"]
    hi = client.get("/patient/me?lang=hi").json()["status"]
    assert hi["language"] == "hi"
    assert hi["happening"] != en["happening"]


def test_patient_view_rejects_unsupported_language(patient_client):
    client, _ = patient_client
    r = client.get("/patient/me?lang=kl")
    assert r.status_code == 400
    assert "supported" in r.json()["detail"]


def test_patient_view_outcome_copy_is_safe(patient_client):
    client, _ = patient_client
    r = client.get("/patient/me?outcome=rejected")
    assert r.status_code == 200
    status = r.json()["status"]
    events = [m["event"] for m in status["messages"]]
    assert "claim_rejected" in events
    text = next(m["text"] for m in status["messages"] if m["event"] == "claim_rejected").lower()
    for alarming in ("denied", "rejected", "unfortunately", "failed"):
        assert alarming not in text


def test_patient_view_at_a_point_in_time(patient_client):
    client, _ = patient_client
    early = client.get("/patient/me?at=0").json()["status"]
    assert early["stage"] == "order"
    assert early["elapsed_min"] == 0
    assert early["eta_min"] is not None


def test_patient_view_requires_a_session():
    with TestClient(app) as anon:
        assert anon.get("/patient/me").status_code == 401


def test_there_is_no_route_that_takes_a_record_id():
    """The IDOR is closed by construction: the endpoint accepts no object identifier."""
    with TestClient(app) as anon:
        assert anon.get("/patient/R0001").status_code == 404
        assert anon.get("/patient/R0002").status_code == 404
