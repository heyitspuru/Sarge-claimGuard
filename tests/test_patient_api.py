from fastapi.testclient import TestClient

from claimguard.api import app

client = TestClient(app)


def _a_record_id() -> str:
    return client.get("/radar/journeys").json()["journeys"][0]["record_id"]


def test_patient_view_returns_plain_language_status():
    r = client.get(f"/patient/{_a_record_id()}")
    assert r.status_code == 200
    body = r.json()
    assert body["synthetic"] is True
    status = body["status"]
    assert status["happening"].strip()
    assert status["next_step"].strip()
    assert status["sla_min"] == 180
    assert status["messages"], "a journey should always have sent at least the pharmacy message"
    assert status["messages"][0]["event"] == "pharmacy_ready"


def test_patient_view_honours_language():
    rid = _a_record_id()
    en = client.get(f"/patient/{rid}?lang=en").json()["status"]
    hi = client.get(f"/patient/{rid}?lang=hi").json()["status"]
    assert hi["language"] == "hi"
    assert hi["happening"] != en["happening"]


def test_patient_view_rejects_unsupported_language():
    r = client.get(f"/patient/{_a_record_id()}?lang=kl")
    assert r.status_code == 400
    assert "supported" in r.json()["detail"]


def test_patient_view_outcome_copy_is_safe():
    r = client.get(f"/patient/{_a_record_id()}?outcome=rejected")
    assert r.status_code == 200
    status = r.json()["status"]
    events = [m["event"] for m in status["messages"]]
    assert "claim_rejected" in events
    text = next(m["text"] for m in status["messages"] if m["event"] == "claim_rejected").lower()
    for alarming in ("denied", "rejected", "unfortunately", "failed"):
        assert alarming not in text


def test_patient_view_at_a_point_in_time():
    rid = _a_record_id()
    early = client.get(f"/patient/{rid}?at=0").json()["status"]
    assert early["stage"] == "order"
    assert early["elapsed_min"] == 0
    assert early["eta_min"] is not None


def test_unknown_patient_record_404s():
    assert client.get("/patient/NOPE-0000").status_code == 404
