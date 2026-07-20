"""ABHA identity linkage and duplicate/fraud flagging (§9-10).

Deliberately **flags, never blocks**. A duplicate (abha_id, admission_date) is usually a
resubmission or a data-entry artifact, not fraud, and a system that silently refuses
legitimate claims harms the patient it exists to help. Flagging routes the claim to a
human; blocking substitutes an automated guess for a judgement that isn't ours to make.

No LLM: identity collision is a deterministic lookup, and a stochastic answer to
"is this the same admission" would be strictly worse.
"""

from claimguard.models import DischargeRecord

DUPLICATE_ADMISSION = "duplicate_admission"
ABHA_MISMATCH = "abha_identity_mismatch"


def admission_key(record: DischargeRecord) -> tuple[str, str]:
    return (record.patient.abha_id, record.admission_date)


def check(record: DischargeRecord, index: dict[tuple[str, str], str]) -> list[str]:
    """Flags for this record against an index of already-seen admissions.

    `index` maps (abha_id, admission_date) -> record_id. Mutated to include this record
    so a run accumulates its own history.
    """
    flags: list[str] = []
    key = admission_key(record)

    seen = index.get(key)
    if seen is not None and seen != record.record_id:
        flags.append(f"{DUPLICATE_ADMISSION}: same ABHA + admission date as {seen}")

    index.setdefault(key, record.record_id)
    return flags


def link_identities(records: list[DischargeRecord]) -> dict[str, list[str]]:
    """abha_id -> record_ids sharing it. The 'identity linkage' half of §9-10."""
    linked: dict[str, list[str]] = {}
    for record in records:
        linked.setdefault(record.patient.abha_id, []).append(record.record_id)
    return linked


def name_conflicts(records: list[DischargeRecord]) -> dict[str, set[str]]:
    """ABHA ids appearing under more than one patient name — an identity red flag."""
    by_abha: dict[str, set[str]] = {}
    for record in records:
        by_abha.setdefault(record.patient.abha_id, set()).add(record.patient.name)
    return {abha: names for abha, names in by_abha.items() if len(names) > 1}
