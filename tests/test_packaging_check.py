from pathlib import Path

from claimguard.eval import runner


def test_run_packaging_check_hits_100_percent_on_golden():
    """CLAUDE.md DoD gate: packaging validity = 100% on the golden set, demonstrable offline.

    Isolates the packager from coder confidence (see run_packaging_check docstring) by scoring
    only the ready+rejected subset, which is fully decidable from documents + codes alone.
    """
    report = runner.run_packaging_check(Path("data/golden"))

    assert report["n"] > 0
    assert report["packaging_validity"] == 1.0
