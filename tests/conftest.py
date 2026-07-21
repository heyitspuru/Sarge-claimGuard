"""Test hygiene: force the deterministic mock LLM provider for every test,
regardless of what .env sets. Keeps the suite offline and free even when a
developer has LLM_PROVIDER=gemini in their .env for real eval runs.

The pin is applied at BOTH times, and it needs both:

  - **Import time (below).** conftest is imported before test modules are
    collected, so this covers module-level code in a test file. Fixtures do not
    exist yet at collection, so a module-level provider call would otherwise hit
    the real API — which is exactly what `tests/integration/test_pipeline.py` did
    for a long time: one real embedding call per suite run, on a file whose own
    docstring promised "no network, no real model calls". It only surfaced when a
    DNS failure turned a 15-second suite into a 23-minute one.
  - **Per test (the fixture).** Restores the pin if an individual test monkeypatches
    the provider, and clears the settings cache on both sides.

db-marked tests still use the real database_url from .env (they connect to a
running Postgres or skip); only the LLM provider is pinned here.
"""
import os

import pytest

from claimguard.config import get_settings

# Before any test module is imported. See the note above — this is load-bearing.
os.environ["LLM_PROVIDER"] = "mock"
get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _force_mock_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _clean_auth_state():
    """Sessions and OTP challenges are process-global, so leaking them between tests
    would let one test authenticate another."""
    from claimguard.auth.deps import CONSENT
    from claimguard.auth.otp import OTPS
    from claimguard.auth.sessions import SESSIONS

    SESSIONS.clear()
    OTPS.clear()
    CONSENT._withdrawn.clear()
    yield
    SESSIONS.clear()
    OTPS.clear()
    CONSENT._withdrawn.clear()


def _first_golden_identity() -> tuple[str, str]:
    """(record_id, abha_id) of the first golden record — a valid synthetic login."""
    import json
    from pathlib import Path

    path = sorted(Path("data/golden").glob("*.json"))[0]
    rec = json.loads(path.read_text(encoding="utf-8"))["record"]
    return rec["record_id"], rec["patient"]["abha_id"]


@pytest.fixture
def staff_client():
    """TestClient with a logged-in hospital staff session."""
    from fastapi.testclient import TestClient

    from claimguard.api import app

    with TestClient(app) as client:
        s = get_settings()
        r = client.post("/auth/staff/login",
                        json={"email": s.staff_email, "password": s.staff_password})
        assert r.status_code == 200, r.text
        yield client


@pytest.fixture
def patient_client():
    """(TestClient, record_id) with a logged-in patient session for that record."""
    from fastapi.testclient import TestClient

    from claimguard.api import app

    record_id, abha = _first_golden_identity()
    with TestClient(app) as client:
        challenge = client.post("/auth/patient/request-otp",
                                json={"identifier": abha}).json()
        r = client.post("/auth/patient/verify-otp", json={
            "challenge_id": challenge["challenge_id"],
            "otp": challenge["simulated_otp"]})
        assert r.status_code == 200, r.text
        yield client, record_id


@pytest.fixture
def db_conn():
    """A live Postgres connection, or a skip that says *why* there isn't one.

    Both db tests used to swallow every exception as "postgres not reachable". That
    hid a real bug for as long as it existed: connect() failed against a bare server
    because the `vector` extension did not exist yet, and CI reported it as an absent
    database. Only a genuine connection failure skips here — anything else raises.
    """
    import psycopg

    from claimguard import db

    try:
        conn = db.connect()
    except (psycopg.OperationalError, psycopg.errors.InsufficientPrivilege) as exc:
        # InsufficientPrivilege too: connect() now runs CREATE EXTENSION, which a managed
        # or non-superuser Postgres refuses. That is an unusable database, not a broken
        # test — the same "skip, and say why" case as an unreachable one.
        pytest.skip(f"postgres unusable for these tests: {exc}")
    db.init_schema(conn)
    yield conn
    conn.close()
