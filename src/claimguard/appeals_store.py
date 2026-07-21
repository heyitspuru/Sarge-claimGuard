"""Drafted appeals and their human review state.

An appeal is a formal communication to an insurer on a patient's behalf. A
model-drafted letter must therefore **never be sent without a human reading it** — the
same reflex as CLAUDE.md's rule that a low-confidence code never reaches submission
unreviewed. So a draft lands in `drafted`, and a person moves it to `approved` or
`declined`.

Drafts are persisted to disk rather than held in memory for two reasons: drafting costs
real provider quota (~20 generate requests/day on the free tier), so re-opening a claim
must not re-spend it; and a committed draft lets the demo show a real grounded appeal
without anyone having to burn a call first.
"""

import json
import time
from pathlib import Path

from claimguard.config import get_settings
from claimguard.models import AppealResult

REVIEW_STATES = ("drafted", "approved", "declined")


def _dir() -> Path:
    return Path(get_settings().data_dir) / "appeals"


def _path(record_id: str) -> Path:
    return _dir() / f"{record_id}.json"


def get(record_id: str) -> dict | None:
    path = _path(record_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def save(record_id: str, appeal: AppealResult, *, drafted_by: str) -> dict:
    """Persist a fresh draft. Always lands in `drafted` — never pre-approved."""
    payload = {
        "record_id": record_id,
        "appeal": appeal.model_dump(),
        "review_state": "drafted",
        "drafted_by": drafted_by,
        "drafted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "reviewed_by": None,
        "reviewed_at": None,
        "review_note": "",
    }
    _dir().mkdir(parents=True, exist_ok=True)
    _path(record_id).write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
    return payload


def review(record_id: str, state: str, *, reviewed_by: str, note: str = "") -> dict | None:
    """Record a human decision on a draft. Returns None if there is no draft."""
    if state not in ("approved", "declined"):
        raise ValueError(f"review state must be approved or declined, got {state!r}")
    payload = get(record_id)
    if payload is None:
        return None
    # A refusal is terminal, not pending. "approved" here would read as "cleared to go to
    # the insurer" while `appeal_text` is empty and there are no citations — a claim that
    # an appeal is on its way when nothing exists. Guarded at the store, not the UI, so
    # every caller (API, CLI, a future batch job) inherits it.
    if payload["appeal"]["status"] == "no_valid_appeal":
        raise ValueError(
            "this draft is the Negotiator declining to appeal — there is no letter to "
            "approve or decline. Nothing is pending."
        )
    payload |= {
        "review_state": state,
        "reviewed_by": reviewed_by,
        "reviewed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "review_note": note,
    }
    _path(record_id).write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
    return payload


def all_drafts() -> dict[str, dict]:
    directory = _dir()
    if not directory.exists():
        return {}
    out: dict[str, dict] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        out[payload["record_id"]] = payload
    return out
