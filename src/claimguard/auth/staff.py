"""Hospital staff credentials.

Seeded from config, with no self-registration — staff accounts in a real deployment come
from the hospital's identity provider, not a signup form.

Hashing is stdlib `hashlib.scrypt`, which is memory-hard and needs no third-party
dependency. Verification is constant-time.

Single tenant: there is one hospital and staff see every record. Records carry no
`hospital_id` today, so a tenancy boundary would be a field with one value rather than a
boundary — documented as a gap in docs/PRODUCTION_READINESS.md instead of faked here.
"""

import hashlib
import secrets
from functools import lru_cache

from claimguard.config import get_settings

_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    candidate = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return secrets.compare_digest(candidate.hex(), digest_hex)


@lru_cache(maxsize=1)
def _stored_credential() -> tuple[str, str]:
    """(email, password_hash), hashed once rather than per login attempt.

    Note honestly: the demo password lives in config as plaintext, so hashing it here
    protects nothing at rest — it exists so the verification path is the shape a real
    credential store would use. The real fix is an identity provider, not a better hash
    (docs/PRODUCTION_READINESS.md §6).
    """
    settings = get_settings()
    return settings.staff_email.strip().lower(), hash_password(settings.staff_password)


def authenticate(email: str, password: str) -> str | None:
    """Staff email on success, None on failure.

    The password hash is always computed, even for an unknown email, so response time
    does not reveal whether an address is registered.
    """
    expected_email, stored = _stored_credential()
    # compare_digest on str raises for non-ASCII, and an email field takes arbitrary
    # input — compare bytes.
    email_ok = secrets.compare_digest(
        (email or "").strip().lower().encode(), expected_email.encode()
    )
    password_ok = verify_password(password or "", stored)
    return expected_email if (email_ok and password_ok) else None
