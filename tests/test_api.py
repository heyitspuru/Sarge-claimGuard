from fastapi.testclient import TestClient

from claimguard.api import app


def test_health():
    assert TestClient(app).get("/health").json() == {"status": "ok"}


def test_placeholder_page():
    r = TestClient(app).get("/")
    assert r.status_code == 200 and "ClaimGuard" in r.text
