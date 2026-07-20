"""Simulated OTP challenge.

**This sends nothing.** There is no SMS gateway and no ABDM connection; the code is
returned in the API response and labelled simulated so the demo is self-contained and
obviously not a real second factor.

Real ABHA OTP is delivered by ABDM to the Aadhaar-linked mobile, which requires
registration as a Health Information User — see docs/AUTH.md. What is faithfully
reproduced here is the *shape*: a challenge id, a short expiry, single use, and a
bounded number of attempts. Those are the properties the rest of the system should be
built against, so swapping in the real delivery channel changes one function.
"""

import secrets
import time
from dataclasses import dataclass, field

from claimguard.config import get_settings


@dataclass
class Challenge:
    record_id: str
    code: str
    created_at: float = field(default_factory=time.time)
    attempts: int = 0
    consumed: bool = False


class OtpStore:
    """# ponytail: in-memory, single process. Same swap path as SessionStore."""

    def __init__(self) -> None:
        self._challenges: dict[str, Challenge] = {}

    def issue(self, record_id: str) -> tuple[str, str]:
        """Returns (challenge_id, code). The code is simulated — nothing is sent."""
        challenge_id = secrets.token_urlsafe(16)
        code = f"{secrets.randbelow(1_000_000):06d}"
        self._challenges[challenge_id] = Challenge(record_id=record_id, code=code)
        return challenge_id, code

    def verify(self, challenge_id: str, code: str) -> tuple[str | None, str]:
        """(record_id, reason). record_id is None on any failure.

        Deliberately returns the same shape for every failure mode so the caller can
        decide how much to disclose; the caller tells the user "invalid or expired"
        without distinguishing which, so this cannot be used to probe validity.
        """
        settings = get_settings()
        challenge = self._challenges.get(challenge_id)
        if challenge is None:
            return None, "unknown_challenge"
        if challenge.consumed:
            return None, "already_used"
        if time.time() - challenge.created_at > settings.otp_ttl_sec:
            del self._challenges[challenge_id]
            return None, "expired"
        if challenge.attempts >= settings.otp_max_attempts:
            del self._challenges[challenge_id]
            return None, "too_many_attempts"

        challenge.attempts += 1
        # constant-time compare so the code cannot be recovered by timing
        if not secrets.compare_digest(challenge.code, code.strip()):
            return None, "wrong_code"

        challenge.consumed = True
        del self._challenges[challenge_id]
        return challenge.record_id, "ok"

    def clear(self) -> None:
        self._challenges.clear()


OTPS = OtpStore()
