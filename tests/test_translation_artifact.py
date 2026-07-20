"""Staleness guard: every patient-facing string must have been back-check validated.

This is the recurring half of the translation-validation design (docs/
TRANSLATION_VALIDATION.md). The back-check itself is a one-shot artifact generator —
the catalogs are static constants, so re-running it in CI would re-prove the same fact
forever at real API cost. What actually needs guarding is the human failure mode:
someone edits or adds a patient-facing string and ships it without revalidating.

So this test is offline and instant. It recomputes hashes from the live catalogs and
fails, naming keys, if any string is unvalidated or has changed since validation.

If it fails, that is not a bug in the test — rerun:
    python -m claimguard validate-translations
and commit the regenerated artifact + sidecar.
"""

import json
from pathlib import Path

import pytest

from claimguard.comms.backcheck import SIDECAR, collect_strings, text_hash

pytestmark = pytest.mark.skipif(
    not Path(SIDECAR).exists(),
    reason="no back-check sidecar yet; run `python -m claimguard validate-translations`",
)


def _recorded() -> dict[str, str]:
    return json.loads(Path(SIDECAR).read_text(encoding="utf-8"))["hashes"]


def test_every_translated_string_has_been_validated():
    recorded = _recorded()
    missing = [f"{r['lang']}:{r['key']}" for r in collect_strings()
               if f"{r['lang']}:{r['key']}" not in recorded]
    assert not missing, (
        f"{len(missing)} patient-facing string(s) have never been back-check validated: "
        f"{missing}. Run `python -m claimguard validate-translations`."
    )


def test_no_validated_string_has_changed_since_validation():
    recorded = _recorded()
    drifted = [
        f"{r['lang']}:{r['key']}"
        for r in collect_strings()
        if (key := f"{r['lang']}:{r['key']}") in recorded
        and recorded[key] != text_hash(r["text"])
    ]
    assert not drifted, (
        f"{len(drifted)} string(s) changed after validation and are now unverified: "
        f"{drifted}. Re-run `python -m claimguard validate-translations` and commit "
        f"the regenerated artifact."
    )


def test_sidecar_has_no_entries_for_strings_that_no_longer_exist():
    """A stale entry means the catalog shrank; the artifact is describing dead copy."""
    live = {f"{r['lang']}:{r['key']}" for r in collect_strings()}
    orphaned = [k for k in _recorded() if k not in live]
    assert not orphaned, f"sidecar references removed strings: {orphaned}"


def test_back_check_artifact_exists_alongside_the_sidecar():
    artifact = Path("docs/TRANSLATION_BACKCHECK.md")
    assert artifact.exists(), "sidecar present but the human-reviewable artifact is missing"
    assert "back-check" in artifact.read_text(encoding="utf-8").lower()
