"""Authentication and — more importantly — authorization.

Authentication asks "who are you". Authorization asks "are you allowed this record",
and that is the question the old API never asked: `/patient/{record_id}` served anyone
who guessed an id, and `/radar/journeys` handed out the list of ids to guess.

The load-bearing test here is `test_patient_cannot_reach_another_patients_claim`.
Everything else supports it.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from claimguard.api import app
from claimguard.auth.deps import CONSENT
from claimguard.auth.identity import _identity_index
from claimguard.auth.otp import OTPS
from claimguard.auth.sessions import SESSIONS
from claimguard.config import get_settings

GOLDEN = Path("data/golden")


@pytest.fixture(autouse=True)
def _clean_state():
    SESSIONS.clear()
    OTPS.clear()
    CONSENT._withdrawn.clear()
    _identity_index.cache_clear()
    yield
    SESSIONS.clear()
    OTPS.clear()
    CONSENT._withdrawn.clear()


def _corpus_identities(n=2) -> list[tuple[str, str, str]]:
    """(record_id, abha_id, policy_number) for the first n golden records."""
    out = []
    for path in sorted(GOLDEN.glob("*.json"))[:n]:
        rec = json.loads(path.read_text(encoding="utf-8"))["record"]
        out.append((rec["record_id"], rec["patient"]["abha_id"],
                    rec["insurance"]["policy_number"]))
    return out


def _login_patient(client: TestClient, identifier: str) -> dict:
    challenge = client.post("/auth/patient/request-otp",
                            json={"identifier": identifier}).json()
    return client.post("/auth/patient/verify-otp", json={
        "challenge_id": challenge["challenge_id"], "otp": challenge["simulated_otp"],
    }).json()


def _login_staff(client: TestClient) -> None:
    s = get_settings()
    r = client.post("/auth/staff/login",
                    json={"email": s.staff_email, "password": s.staff_password})
    assert r.status_code == 200, r.text


# --- the boundary that matters ------------------------------------------------


def test_patient_cannot_reach_another_patients_claim():
    """There is no route that takes a record_id, so there is nothing to attack."""
    identities = _corpus_identities(2)
    if len(identities) < 2:
        pytest.skip("needs at least two golden records")
    (record_a, abha_a, _), (record_b, _, _) = identities

    with TestClient(app) as client:
        _login_patient(client, abha_a)

        mine = client.get("/patient/me")
        assert mine.status_code == 200
        assert mine.json()["status"]["record_id"] == record_a

        # the old shape is gone entirely — not merely guarded
        assert client.get(f"/patient/{record_b}").status_code == 404
        assert client.get(f"/patient/{record_a}").status_code == 404

        # and a patient cannot reach the record list that would enable enumeration
        assert client.get("/radar/journeys").status_code == 403


def test_unauthenticated_access_is_refused_everywhere():
    with TestClient(app) as client:
        assert client.get("/radar/journeys").status_code == 401
        assert client.get("/radar/journey/R0001").status_code == 401
        assert client.get("/patient/me").status_code == 401
        assert client.get("/auth/me").status_code == 401


def test_health_and_index_stay_public():
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/").status_code == 200


def test_staff_session_cannot_use_the_patient_endpoint():
    with TestClient(app) as client:
        _login_staff(client)
        assert client.get("/radar/journeys").status_code == 200
        assert client.get("/patient/me").status_code == 403


# --- the synthetic-only rule --------------------------------------------------


def test_identifier_outside_the_corpus_is_refused():
    """A real ABHA id must never be accepted — that would ingest real personal data."""
    with TestClient(app) as client:
        r = client.post("/auth/patient/request-otp",
                        json={"identifier": "12-3456-7890-1234"})
        assert r.status_code == 400
        assert "synthetic" in r.json()["detail"].lower()


def test_rejection_does_not_echo_the_identifier_back():
    """A rejected real identifier must not survive in the response or a log line."""
    probe = "99-8888-7777-6666"
    with TestClient(app) as client:
        r = client.post("/auth/patient/request-otp", json={"identifier": probe})
        assert probe not in r.text
        assert probe.replace("-", "") not in r.text


def test_empty_identifier_is_refused():
    with TestClient(app) as client:
        assert client.post("/auth/patient/request-otp",
                           json={"identifier": "   "}).status_code == 400


def test_policy_number_is_accepted_as_well_as_abha():
    (record_id, _, policy) = _corpus_identities(1)[0]
    with TestClient(app) as client:
        assert _login_patient(client, policy)["record_id"] == record_id


def test_abha_id_is_accepted_with_or_without_separators():
    (record_id, abha, _) = _corpus_identities(1)[0]
    with TestClient(app) as client:
        assert _login_patient(client, abha.replace("-", ""))["record_id"] == record_id


# --- OTP behaviour ------------------------------------------------------------


def test_wrong_code_is_refused():
    (_, abha, _) = _corpus_identities(1)[0]
    with TestClient(app) as client:
        challenge = client.post("/auth/patient/request-otp",
                                json={"identifier": abha}).json()
        r = client.post("/auth/patient/verify-otp", json={
            "challenge_id": challenge["challenge_id"], "otp": "000000"})
        assert r.status_code == 401
        assert client.get("/patient/me").status_code == 401


def test_code_cannot_be_replayed():
    (_, abha, _) = _corpus_identities(1)[0]
    with TestClient(app) as client:
        challenge = client.post("/auth/patient/request-otp",
                                json={"identifier": abha}).json()
        body = {"challenge_id": challenge["challenge_id"],
                "otp": challenge["simulated_otp"]}
        assert client.post("/auth/patient/verify-otp", json=body).status_code == 200
        assert client.post("/auth/patient/verify-otp", json=body).status_code == 401


def test_attempts_are_bounded():
    (_, abha, _) = _corpus_identities(1)[0]
    limit = get_settings().otp_max_attempts
    with TestClient(app) as client:
        challenge = client.post("/auth/patient/request-otp",
                                json={"identifier": abha}).json()
        cid = challenge["challenge_id"]
        for _ in range(limit):
            client.post("/auth/patient/verify-otp", json={"challenge_id": cid,
                                                           "otp": "000000"})
        # even the correct code is refused once the challenge is burned
        r = client.post("/auth/patient/verify-otp",
                        json={"challenge_id": cid, "otp": challenge["simulated_otp"]})
        assert r.status_code == 401


def test_expired_challenge_is_refused(monkeypatch):
    (_, abha, _) = _corpus_identities(1)[0]
    monkeypatch.setenv("OTP_TTL_SEC", "0")
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            challenge = client.post("/auth/patient/request-otp",
                                    json={"identifier": abha}).json()
            r = client.post("/auth/patient/verify-otp", json={
                "challenge_id": challenge["challenge_id"],
                "otp": challenge["simulated_otp"]})
            assert r.status_code == 401
    finally:
        get_settings.cache_clear()


# --- staff credentials --------------------------------------------------------


def test_wrong_staff_password_is_refused():
    s = get_settings()
    with TestClient(app) as client:
        r = client.post("/auth/staff/login",
                        json={"email": s.staff_email, "password": "wrong"})
        assert r.status_code == 401
        assert client.get("/radar/journeys").status_code == 401


def test_unknown_staff_email_is_refused():
    with TestClient(app) as client:
        assert client.post("/auth/staff/login", json={
            "email": "nobody@elsewhere.test", "password": "x"}).status_code == 401


# --- session lifecycle --------------------------------------------------------


def test_logout_revokes_server_side_not_just_the_cookie():
    (_, abha, _) = _corpus_identities(1)[0]
    with TestClient(app) as client:
        _login_patient(client, abha)
        token = client.cookies.get("cg_session")
        assert client.get("/patient/me").status_code == 200

        client.post("/auth/logout")
        assert client.get("/patient/me").status_code == 401

        # replaying the captured cookie must also fail — the server forgot it
        client.cookies.set("cg_session", token)
        assert client.get("/patient/me").status_code == 401


def test_forged_cookie_is_refused():
    with TestClient(app) as client:
        client.cookies.set("cg_session", "not-a-real-token")
        assert client.get("/patient/me").status_code == 401


def test_whoami_reports_the_principal():
    (record_id, abha, _) = _corpus_identities(1)[0]
    with TestClient(app) as client:
        _login_patient(client, abha)
        me = client.get("/auth/me").json()
        assert me["kind"] == "patient"
        assert me["record_id"] == record_id


# --- consent (§9-7) now actually reaches the API ------------------------------


def test_consent_withdrawal_kills_a_live_session():
    """Halting the pipeline while leaving the patient logged in would be a withdrawal
    in name only."""
    (record_id, abha, _) = _corpus_identities(1)[0]
    with TestClient(app) as client:
        _login_patient(client, abha)
        assert client.get("/patient/me").status_code == 200

        CONSENT.withdraw(record_id)

        # the request that discovers the withdrawal is told why, and revokes the session
        assert client.get("/patient/me").status_code == 403
        # every request after that is simply unauthenticated — the session is gone,
        # not merely refused
        assert client.get("/auth/me").status_code == 401
        assert client.get("/patient/me").status_code == 401


def test_withdrawn_patient_cannot_log_back_in():
    (record_id, abha, _) = _corpus_identities(1)[0]
    CONSENT.withdraw(record_id)
    with TestClient(app) as client:
        challenge = client.post("/auth/patient/request-otp",
                                json={"identifier": abha}).json()
        r = client.post("/auth/patient/verify-otp", json={
            "challenge_id": challenge["challenge_id"],
            "otp": challenge["simulated_otp"]})
        assert r.status_code == 403


# --- cookie hardening ---------------------------------------------------------


def test_session_cookie_is_httponly_and_samesite():
    (_, abha, _) = _corpus_identities(1)[0]
    with TestClient(app) as client:
        challenge = client.post("/auth/patient/request-otp",
                                json={"identifier": abha}).json()
        r = client.post("/auth/patient/verify-otp", json={
            "challenge_id": challenge["challenge_id"],
            "otp": challenge["simulated_otp"]})
        cookie_header = r.headers["set-cookie"].lower()
        assert "httponly" in cookie_header, "JS-readable session cookie is XSS-exfiltratable"
        assert "samesite=lax" in cookie_header, "no CSRF protection on the cookie"
