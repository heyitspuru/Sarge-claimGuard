"""Consent withdrawal and erasure (§9-7).

A patient can withdraw consent at any point, including mid-pipeline. Two obligations
follow, and they are different: **stop** (do no further processing) and **erase**
(remove what was already produced). Honouring only the first leaves derived artifacts
sitting in stores after the patient asked for them gone.

The check is applied BETWEEN orchestrator steps rather than once at entry, because a
withdrawal that arrives while the claim is halfway through must still be honoured — a
gate that only fires at the front door is not a withdrawal mechanism.

Scope: this is the *mechanism*, exercised against synthetic data. A real deployment
needs ABDM consent-manager integration as the source of truth — see
docs/PRODUCTION_READINESS.md §1.
"""


class ConsentWithdrawn(Exception):
    """Raised when processing is attempted for a record whose consent was withdrawn."""


class ConsentRegistry:
    """In-memory consent state.

    # ponytail: in-memory set; back it with the consent manager when one exists.
    """

    def __init__(self, withdrawn: set[str] | None = None):
        self._withdrawn: set[str] = set(withdrawn or ())

    def withdraw(self, record_id: str) -> None:
        self._withdrawn.add(record_id)

    def is_withdrawn(self, record_id: str) -> bool:
        return record_id in self._withdrawn

    def __call__(self, record_id: str) -> bool:
        """Callable form so it drops straight into PipelineDeps.consent."""
        return self.is_withdrawn(record_id)


def erase(record_id: str, *stores: dict, audit_log: list | None = None) -> dict:
    """Purge every trace of a record from the given stores and the audit log.

    Returns a receipt of what was removed. A withdrawal the system cannot evidence is
    not auditable, and "we deleted it, trust us" is not an erasure interface.
    """
    removed_from = []
    for i, store in enumerate(stores):
        if record_id in store:
            del store[record_id]
            removed_from.append(i)

    audit_removed = 0
    if audit_log is not None:
        before = len(audit_log)
        audit_log[:] = [e for e in audit_log if e.get("record_id") != record_id]
        audit_removed = before - len(audit_log)

    return {
        "record_id": record_id,
        "stores_purged": len(removed_from),
        "audit_entries_removed": audit_removed,
        "erased": True,
    }
