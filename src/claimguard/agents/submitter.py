import hashlib
from claimguard.models import ClaimPackage, SubmissionResult


def submit(package: ClaimPackage, store: dict) -> SubmissionResult:
    """
    Deterministic NHCX submission simulator.

    Args:
        package: ClaimPackage to submit (must have status == "ready")
        store: dict mapping record_id to SubmissionResult for idempotency

    Returns:
        SubmissionResult with submission_id, status="adjudicated", and outcome

    Raises:
        ValueError: if package.status != "ready"
    """
    if package.status != "ready":
        raise ValueError(f"cannot submit package with status {package.status}")

    # Idempotency: return existing result if already submitted
    if package.record_id in store:
        return store[package.record_id]

    # Deterministic adjudication via SHA1 hash
    h = int(hashlib.sha1(package.record_id.encode()).hexdigest(), 16) % 10

    if h <= 6:
        outcome = "approved"
    elif h <= 8:
        outcome = "partial"
    else:
        outcome = "rejected"

    result = SubmissionResult(
        record_id=package.record_id,
        submission_id=f"SIM-{package.record_id}",
        status="adjudicated",
        outcome=outcome,
    )

    # Store for idempotency
    store[package.record_id] = result
    return result
