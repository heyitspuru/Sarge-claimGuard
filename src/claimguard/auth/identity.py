"""Resolving a login identifier to a synthetic record.

Patients authenticate with an **ABHA id** (India's health account number) or their
**policy number**. Both are 1:1 with a record across the synthetic corpus, so either is
a usable natural key.

SAFETY RULE, enforced here and tested: an identifier that does not match a record in the
synthetic corpus is **rejected**. A demo that accepted a real 14-digit ABHA number would
ingest real personal data from the first curious visitor, which CLAUDE.md prime
directive 3 forbids outright. Rejecting unknown identifiers is what makes that
structural rather than aspirational.

Identifiers are **never logged**, not even on a failed attempt — a rejected real ABHA id
sitting in a log file is exactly the data we refused to accept.

Real ABHA authentication is not this. It runs through ABDM as a registered Health
Information User, with the OTP delivered to the Aadhaar/mobile on file — the same
organisation-level gate that blocks real NHCX submission (docs/NHCX_ACCESS.md). This is
a faithful simulator of the shape of that flow, and is labelled as one everywhere it
surfaces.
"""

import json
from functools import lru_cache
from pathlib import Path

from claimguard.config import get_settings


@lru_cache(maxsize=1)
def _identity_index() -> dict[str, str]:
    """`abha_id` and `policy_number` -> record_id, over the whole golden corpus.

    Cached: the corpus is static at runtime, and re-reading 200 files per login attempt
    would make the login endpoint a denial-of-service amplifier.
    """
    golden = Path(get_settings().data_dir) / "golden"
    index: dict[str, str] = {}
    if not golden.exists():
        return index
    for path in sorted(golden.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))["record"]
        except (json.JSONDecodeError, KeyError):
            continue
        record_id = record["record_id"]
        index[_normalise(record["patient"]["abha_id"])] = record_id
        index[_normalise(record["insurance"]["policy_number"])] = record_id
    return index


def _normalise(identifier: str) -> str:
    """Case- and separator-insensitive. People type ABHA ids with and without dashes."""
    return "".join(ch for ch in identifier if ch.isalnum()).upper()


def resolve(identifier: str) -> str | None:
    """record_id for this ABHA id or policy number, or None if it is not in the corpus.

    None means "refuse" — never "create" and never "look up elsewhere".
    """
    if not identifier or not identifier.strip():
        return None
    return _identity_index().get(_normalise(identifier))


def is_synthetic(identifier: str) -> bool:
    return resolve(identifier) is not None
