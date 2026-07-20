"""Server-side sessions with opaque tokens.

Why server-side rather than a JWT: **revocation**. Consent withdrawal (§9-7) must stop
processing *and* kill any live session, and a self-contained token cannot be withdrawn
without a server-side denylist — which is a session store with extra steps. Health data
under DPDP makes that a requirement rather than a preference.

The token carries no claims, so there is nothing to sign and no signing library is
needed: it is `secrets.token_urlsafe(32)` looked up in a store. It rides in an httpOnly
cookie, so an XSS bug cannot read it the way it could read a token in localStorage.
"""

import secrets
import time
from dataclasses import dataclass, field

from claimguard.config import get_settings

COOKIE_NAME = "cg_session"


@dataclass
class Principal:
    """Who is calling. `record_id` is set for patients and None for staff."""

    kind: str  # "patient" | "staff"
    subject: str  # record_id for a patient, email for staff
    record_id: str | None = None
    created_at: float = field(default_factory=time.time)

    @property
    def is_patient(self) -> bool:
        return self.kind == "patient"

    @property
    def is_staff(self) -> bool:
        return self.kind == "staff"


class SessionStore:
    """# ponytail: in-memory dict — sessions die on restart and don't span replicas.
    Swap for a Postgres table (or Redis) when either matters; callers only touch the
    methods below, so the change stays here.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Principal] = {}

    def create(self, principal: Principal) -> str:
        token = secrets.token_urlsafe(32)
        self._sessions[token] = principal
        return token

    def get(self, token: str | None) -> Principal | None:
        if not token:
            return None
        principal = self._sessions.get(token)
        if principal is None:
            return None
        ttl = get_settings().session_ttl_min * 60
        if time.time() - principal.created_at > ttl:
            del self._sessions[token]
            return None
        return principal

    def revoke(self, token: str | None) -> bool:
        if token and token in self._sessions:
            del self._sessions[token]
            return True
        return False

    def revoke_for_record(self, record_id: str) -> int:
        """Kill every session for a record. This is what makes consent withdrawal real:
        halting the pipeline while leaving the patient's session live would be a
        withdrawal in name only."""
        doomed = [t for t, p in self._sessions.items() if p.record_id == record_id]
        for token in doomed:
            del self._sessions[token]
        return len(doomed)

    def clear(self) -> None:
        self._sessions.clear()


SESSIONS = SessionStore()
