import json
from pathlib import Path

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from claimguard.auth import identity, otp, staff
from claimguard.auth.deps import CONSENT, current_principal, require_patient, require_staff
from claimguard.auth.sessions import COOKIE_NAME, SESSIONS, Principal
from claimguard import advocacy, appeals_store, llm
from claimguard import appeal as appeal_mod
from claimguard.agents.submitter import submit
from claimguard.comms import LANGUAGES, advocacy_messages, patient_status
from claimguard.compliance_radar import radar
from claimguard.config import get_settings
from claimguard.coverage import PolicyRetriever, load_policies
from claimguard.models import ClaimPackage

app = FastAPI(title="ClaimGuard")

# The Vite dev server proxies /api -> here, so the browser sees one origin and the
# session cookie is same-site. These origins remain for direct access during dev.
# allow_credentials requires explicit origins — a wildcard is rejected by browsers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_GOLDEN = Path(__file__).resolve().parents[2] / "data" / "golden"

_BASELINE = {
    "preauth_sla_min": radar.PREAUTH_SLA_MIN,
    "discharge_sla_min": radar.DISCHARGE_SLA_MIN,
    "prebreach_min": radar.PREBREACH_MIN,
}


def _record_index() -> dict[str, str]:
    """record_id -> claim_type for the golden set; falls back to synthetic ids."""
    idx: dict[str, str] = {}
    if _GOLDEN.exists():
        for f in sorted(_GOLDEN.glob("*.json"))[:50]:
            g = json.loads(f.read_text(encoding="utf-8"))
            rec = g.get("record", {})
            idx[rec.get("record_id", f.stem)] = rec.get("claim_type", "cashless")
    if not idx:
        idx = {f"R{i:04d}": ("cashless" if i % 2 else "reimbursement") for i in range(30)}
    return idx


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,  # unreadable from JS, so XSS cannot exfiltrate it
        samesite="lax",  # blocks cross-site form CSRF on the POST routes
        secure=settings.cookie_secure,
        max_age=settings.session_ttl_min * 60,
        path="/",
    )


# --- auth ---------------------------------------------------------------------


class OtpRequest(BaseModel):
    identifier: str  # ABHA id or policy number


class OtpVerify(BaseModel):
    challenge_id: str
    otp: str


class StaffLogin(BaseModel):
    email: str
    password: str


@app.post("/auth/patient/request-otp")
def request_otp(body: OtpRequest):
    """Start a patient login. SIMULATED — nothing is sent anywhere.

    An identifier that is not in the synthetic corpus is refused. A demo that accepted a
    real ABHA number would ingest real personal data from the first curious visitor.
    The identifier is never logged, including on rejection.
    """
    record_id = identity.resolve(body.identifier)
    if record_id is None:
        raise HTTPException(
            status_code=400,
            detail="Unknown identifier. This build only accepts synthetic identifiers "
                   "from its own demo corpus — never enter a real ABHA id or policy number.",
        )
    challenge_id, code = otp.OTPS.issue(record_id)
    return {
        "challenge_id": challenge_id,
        "simulated": True,
        "simulated_otp": code,
        "note": "Simulated OTP — shown here because nothing is sent. Real ABHA delivery "
                "requires ABDM registration as a Health Information User (docs/AUTH.md).",
    }


@app.post("/auth/patient/verify-otp")
def verify_otp(body: OtpVerify, response: Response):
    record_id, _reason = otp.OTPS.verify(body.challenge_id, body.otp)
    if record_id is None:
        # One message for every failure mode, so this cannot be used to probe which
        # challenge ids or codes are valid.
        raise HTTPException(status_code=401, detail="invalid or expired code")
    if CONSENT.is_withdrawn(record_id):
        raise HTTPException(status_code=403, detail="consent withdrawn for this record")

    token = SESSIONS.create(Principal(kind="patient", subject=record_id, record_id=record_id))
    _set_session_cookie(response, token)
    return {"kind": "patient", "record_id": record_id}


@app.post("/auth/staff/login")
def staff_login(body: StaffLogin, response: Response):
    email = staff.authenticate(body.email, body.password)
    if email is None:
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = SESSIONS.create(Principal(kind="staff", subject=email))
    _set_session_cookie(response, token)
    return {"kind": "staff", "email": email}


@app.post("/auth/logout")
def logout(response: Response, cg_session: str | None = Cookie(default=None)):
    """Revoke server-side, then clear the cookie.

    Clearing the cookie alone would leave the session valid for anyone who captured the
    token — the revocation is the part that matters, and is the reason these are
    server-side sessions rather than self-contained tokens.
    """
    revoked = SESSIONS.revoke(cg_session)
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True, "revoked": revoked}


@app.get("/auth/me")
def whoami(principal: Principal = Depends(current_principal)):
    return {"kind": principal.kind, "subject": principal.subject,
            "record_id": principal.record_id}


# --- public -------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index():
    return ("<h1>ClaimGuard API</h1><p>Authentication required. Staff: "
            "<code>/radar/*</code>. Patients: <code>/patient/me</code>. "
            "Login is a labelled simulator — see <code>docs/AUTH.md</code>.</p>")


# --- hospital staff only ------------------------------------------------------


@app.get("/radar/journeys")
def radar_journeys(_: Principal = Depends(require_staff)):
    """Operational view over every record. Staff only — this list is precisely the
    enumeration a patient would need to read other patients' claims."""
    reports = [
        radar.analyze(radar.generate_journey(rid, ctype)).model_dump()
        for rid, ctype in _record_index().items()
    ]
    reports.sort(key=lambda r: r["pre_submission_delay_min"], reverse=True)
    return {"synthetic": True, "baseline": _BASELINE, "journeys": reports}


@app.get("/radar/journey/{record_id}")
def radar_journey(record_id: str, _: Principal = Depends(require_staff)):
    claim_type = _record_index().get(record_id)
    if claim_type is None:
        raise HTTPException(status_code=404, detail=f"unknown record_id {record_id}")
    journey = radar.generate_journey(record_id, claim_type)
    return {
        "synthetic": True,
        "journey": journey.model_dump(),
        "report": radar.analyze(journey).model_dump(),
        "baseline": _BASELINE,
    }


# --- hospital console ---------------------------------------------------------


class AppealReview(BaseModel):
    state: str  # approved | declined
    note: str = ""


def _queue_row(record_id: str, claim_type: str) -> dict | None:
    """One claim's console summary, or None when nothing needs a human.

    "Needs a human" is deliberately narrow and derived from facts we actually have: the
    insurer declined or part-paid, or the claim breached its SLA. Inventing softer
    signals would fill the queue with noise and teach staff to ignore it.
    """
    outcome = advocacy.outcome_for(record_id)
    report = radar.analyze(radar.generate_journey(record_id, claim_type))
    draft = appeals_store.get(record_id)

    denied = outcome in ("partial", "rejected")
    if not denied and report.breach_status != "breach":
        return None

    state = advocacy.advocacy_state(record_id)
    if not denied:
        action = "sla_breach"
    elif state["state"] == "no_valid_appeal":
        action = "no_appeal_available"
    elif draft is None:
        action = "needs_draft"
    elif draft["review_state"] == "drafted":
        action = "needs_review"
    else:
        action = draft["review_state"]

    return {
        "record_id": record_id,
        "claim_type": claim_type,
        "outcome": outcome,
        "breach_status": report.breach_status,
        "pre_submission_delay_min": report.pre_submission_delay_min,
        "advocacy_state": state["state"],
        "review_state": draft["review_state"] if draft else None,
        "action": action,
    }


@app.get("/claims/queue")
def claims_queue(_: Principal = Depends(require_staff)):
    """What actually needs a person, most urgent first."""
    rows = [r for rid, ctype in _record_index().items()
            if (r := _queue_row(rid, ctype)) is not None]
    priority = {"needs_review": 0, "needs_draft": 1, "sla_breach": 2,
                "no_appeal_available": 3, "approved": 4, "declined": 5}
    rows.sort(key=lambda r: (priority.get(r["action"], 9),
                             -r["pre_submission_delay_min"]))
    return {"synthetic": True, "queue": rows}


@app.get("/claims/{record_id}")
def claim_detail(record_id: str, _: Principal = Depends(require_staff)):
    claim_type = _record_index().get(record_id)
    if claim_type is None:
        raise HTTPException(status_code=404, detail=f"unknown record_id {record_id}")

    journey = radar.generate_journey(record_id, claim_type)
    return {
        "synthetic": True,
        "record_id": record_id,
        "claim_type": claim_type,
        "outcome": advocacy.outcome_for(record_id),
        "report": radar.analyze(journey).model_dump(),
        "advocacy": advocacy.advocacy_state(record_id),
        "appeal": appeals_store.get(record_id),
        "consent_withdrawn": CONSENT.is_withdrawn(record_id),
    }


@app.post("/claims/{record_id}/appeal")
def draft_claim_appeal(record_id: str, principal: Principal = Depends(require_staff)):
    """Run the Negotiator for this claim and store the draft for review.

    Costs real provider quota, so it is an explicit staff action rather than something
    that happens on page load. The result is stored, so re-opening the claim is free.
    """
    claim_type = _record_index().get(record_id)
    if claim_type is None:
        raise HTTPException(status_code=404, detail=f"unknown record_id {record_id}")

    record = advocacy._load_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="record not available")

    result = submit(ClaimPackage(record_id=record_id, status="ready"), {})
    if result.outcome not in appeal_mod.APPEALABLE_OUTCOMES:
        raise HTTPException(status_code=400,
                            detail=f"claim outcome is {result.outcome}; nothing to appeal")

    # The mock provider returns an empty completion, which the grounding gate correctly
    # downgrades to `no_valid_appeal` — indistinguishable in the UI from the Negotiator
    # examining a case and genuinely declining it. Refusing outright is the honest
    # behaviour: a fake refusal would undermine the one property this agent exists for.
    if get_settings().llm_provider == "mock":
        raise HTTPException(
            status_code=400,
            detail="Drafting needs a real provider. This API is running on the mock "
                   "provider, which would return an empty completion and look like an "
                   "honest refusal. Set LLM_PROVIDER=gemini (and GEMINI_API_KEY) and "
                   "restart the api container.",
        )

    policies = load_policies(Path(get_settings().data_dir) / "policies")
    retriever = PolicyRetriever(policies, llm.embed)
    handler = appeal_mod.make_appeal_handler(policies, retriever, llm.complete)

    try:
        appeal = handler(record, result)
    except Exception as exc:
        if llm.is_quota_error(exc):
            raise HTTPException(
                status_code=503,
                detail=f"Provider daily quota exhausted ({llm.FREE_TIER_DAILY_GENERATE} "
                       f"generate requests/day on the free tier). Try again tomorrow.",
            ) from exc
        raise HTTPException(status_code=502, detail="could not draft an appeal") from exc

    if appeal is None:
        raise HTTPException(status_code=400, detail="nothing to appeal for this claim")

    try:
        return appeals_store.save(record_id, appeal, drafted_by=principal.subject)
    except OSError as exc:
        # Losing a draft here means the provider call that produced it was spent for
        # nothing, so say exactly what is wrong rather than returning a bare 500.
        raise HTTPException(
            status_code=500,
            detail=f"Drafted the appeal but could not store it: {exc.strerror}. "
                   f"The appeals directory must be writable (see docker-compose.yml — "
                   f"data/ is mounted read-only with data/appeals writable on top).",
        ) from exc


@app.post("/claims/{record_id}/appeal/review")
def review_claim_appeal(record_id: str, body: AppealReview,
                        principal: Principal = Depends(require_staff)):
    """A human decides whether the drafted appeal actually goes to the insurer."""
    # The store owns what is reviewable (valid states, and that a refusal is terminal);
    # duplicating the rules here would let the two drift apart.
    try:
        payload = appeals_store.review(record_id, body.state,
                                        reviewed_by=principal.subject, note=body.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if payload is None:
        raise HTTPException(status_code=404, detail="no draft to review")
    return payload


# --- patient ------------------------------------------------------------------


@app.get("/patient/me")
def patient_view(lang: str = "en", outcome: str | None = None, at: int | None = None,
                 principal: Principal = Depends(require_patient)):
    """The authenticated patient's own claim.

    The record comes from the SESSION, never from the URL. There is deliberately no
    `/patient/{record_id}` route: an endpoint that takes no object identifier cannot
    have an insecure-direct-object-reference bug, which is a stronger guarantee than
    remembering to check ownership on one that does.
    """
    if lang not in LANGUAGES:
        raise HTTPException(status_code=400,
                            detail=f"unsupported lang {lang}; supported: {list(LANGUAGES)}")
    record_id = principal.record_id
    claim_type = _record_index().get(record_id)
    if claim_type is None:
        raise HTTPException(status_code=404, detail="record not available")

    journey = radar.generate_journey(record_id, claim_type)
    report = radar.analyze(journey)

    # The insurer's decision is deterministic, so the patient view and the pipeline can
    # never disagree about what happened. `outcome` stays overridable for demos.
    decided = outcome or advocacy.outcome_for(record_id)
    status = patient_status(journey, report, language=lang, now_minutes=at, outcome=decided)

    # Advocacy track: a lead when the decision lands, the full story once the appeal is
    # filed. Resolved-then-reported — see advocacy.py for why.
    state = advocacy.advocacy_state(record_id)
    decision_at = next((s.at_minutes for s in journey.stages if s.stage == "decision"), 0)
    track = advocacy_messages(record_id, decision_at, state["state"], language=lang,
                               filed_after_min=state["filed_after_min"])

    return {
        "synthetic": True,
        "languages": list(LANGUAGES),
        "status": status.model_dump(),
        "advocacy": {
            **state,
            "messages": [m.model_dump() for m in track],
            # The insurer's reply to an appeal is NOT modelled — saying so beats
            # letting a UI imply a resolution that never happened.
            "outcome_of_appeal": None,
        },
    }
