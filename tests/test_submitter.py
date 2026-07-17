import pytest
from claimguard.agents.submitter import submit
from claimguard.models import ClaimPackage, SubmissionResult


def test_non_ready_package_raises_error():
    """Non-ready package (status != 'ready') raises ValueError."""
    package = ClaimPackage(
        record_id="R0001",
        status="rejected",
        fhir_claim={"resourceType": "Claim"},
    )
    store = {}
    with pytest.raises(ValueError, match="cannot submit package with status rejected"):
        submit(package, store)


def test_idempotency():
    """Two submit calls with same ready package return equal results and store has one entry."""
    package = ClaimPackage(
        record_id="R0001",
        status="ready",
        fhir_claim={"resourceType": "Claim"},
    )
    store = {}

    result1 = submit(package, store)
    result2 = submit(package, store)

    # Results should be equal
    assert result1.record_id == result2.record_id
    assert result1.submission_id == result2.submission_id
    assert result1.status == result2.status
    assert result1.outcome == result2.outcome

    # Store should have exactly one entry
    assert len(store) == 1
    assert "R0001" in store
    assert store["R0001"] is result1  # Same object reference


def test_outcome_distribution():
    """Build 100 ready packages; assert set of outcomes contains all three: approved, partial, rejected."""
    store = {}
    outcomes = set()

    for i in range(100):
        record_id = f"R{i:04d}"
        package = ClaimPackage(
            record_id=record_id,
            status="ready",
            fhir_claim={"resourceType": "Claim"},
        )
        result = submit(package, store)
        outcomes.add(result.outcome)

    # Should have all three outcomes represented
    assert "approved" in outcomes
    assert "partial" in outcomes
    assert "rejected" in outcomes

    # Store should have exactly 100 entries
    assert len(store) == 100
