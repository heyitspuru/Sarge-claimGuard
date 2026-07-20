"""FastAPI dependencies — **this is the security boundary.**

Route guards in the React app are UX: they decide what to render, and an attacker never
runs them. Everything that actually protects data is enforced here, on the server, on
every request.

Consent is checked at the same point. `ConsentRegistry` existed and was tested since
§9-7 but was never wired into the API, so a patient who withdrew consent stayed fully
readable over HTTP. Withdrawal now also revokes that patient's live sessions — halting
the pipeline while leaving them logged in would be a withdrawal in name only.
"""

from fastapi import Cookie, Depends, HTTPException

from claimguard.auth.sessions import SESSIONS, Principal
from claimguard.consent import ConsentRegistry

# Process-wide consent state, shared with the API layer.
# ponytail: in-memory like the session store; same swap path to Postgres.
CONSENT = ConsentRegistry()


def current_principal(cg_session: str | None = Cookie(default=None)) -> Principal:
    """The authenticated caller, or 401. Never returns an anonymous principal —
    callers must not have to remember to check."""
    principal = SESSIONS.get(cg_session)
    if principal is None:
        raise HTTPException(status_code=401, detail="authentication required")

    # A withdrawal that arrives mid-session takes effect on the next request.
    if principal.record_id and CONSENT.is_withdrawn(principal.record_id):
        SESSIONS.revoke_for_record(principal.record_id)
        raise HTTPException(status_code=403, detail="consent withdrawn for this record")

    return principal


def require_patient(principal: Principal = Depends(current_principal)) -> Principal:
    if not principal.is_patient:
        raise HTTPException(status_code=403, detail="patient session required")
    return principal


def require_staff(principal: Principal = Depends(current_principal)) -> Principal:
    if not principal.is_staff:
        raise HTTPException(status_code=403, detail="hospital staff session required")
    return principal
