from claimguard.auth.deps import CONSENT, current_principal, require_patient, require_staff
from claimguard.auth.identity import is_synthetic, resolve
from claimguard.auth.otp import OTPS
from claimguard.auth.sessions import COOKIE_NAME, SESSIONS, Principal

__all__ = [
    "CONSENT",
    "COOKIE_NAME",
    "OTPS",
    "SESSIONS",
    "Principal",
    "current_principal",
    "is_synthetic",
    "require_patient",
    "require_staff",
    "resolve",
]
