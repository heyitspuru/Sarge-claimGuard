"""Bridge from a pipeline denial to a clause-grounded appeal.

Closes the loop the project exists for: a claim that comes back partial or rejected
should raise an appeal automatically, not wait for someone to notice.

Kept OUT of both the Submitter and the orchestrator on purpose. The Submitter is bound
by a hard rule — no LLM, deterministic, idempotent — and constructing an appeal is
neither of the first two. The orchestrator, for its part, has no business knowing how
policy clauses are shaped. So the orchestrator holds a single opaque callable and this
module supplies it.

The simulated insurer's denial reason is derived **deterministically** from the
patient's real policy clauses, so an auto-raised appeal is grounded against the same
corpus the Negotiator retrieves from. A denial citing an invented clause would make the
whole exercise circular.
"""

import hashlib
from collections.abc import Callable

from claimguard.agents.negotiator import draft_appeal
from claimguard.models import (
    AppealResult,
    DenialScenario,
    DischargeRecord,
    InsurerDecision,
    SubmissionResult,
)

APPEALABLE_OUTCOMES = ("partial", "rejected")

# Clause types an insurer plausibly denies on, most-preferred first. Coverage clauses
# are excluded: denying a claim by citing the clause that covers it is not a scenario.
_DENIAL_CLAUSE_TYPES = ("sub_limit", "exclusion", "waiting_period")

_REASON = {
    "partial": ("Payment limited under {clause_type} clause {clause_id}. "
                "Approved amount reflects the applicable limit."),
    "rejected": ("Claim not admissible under {clause_type} clause {clause_id}."),
}


def _policy_for(record: DischargeRecord, policies: list[dict]) -> dict | None:
    for policy in policies:
        if (policy["insurer_id"] == record.insurance.insurer_id
                and policy["plan_id"] == record.insurance.plan_id):
            return policy
    return None


def _pick_clause(record: DischargeRecord, policy: dict) -> dict | None:
    """Deterministic clause choice, stable for a given record."""
    candidates = [c for c in policy["clauses"] if c["clause_type"] in _DENIAL_CLAUSE_TYPES]
    if not candidates:
        return None
    candidates.sort(key=lambda c: (_DENIAL_CLAUSE_TYPES.index(c["clause_type"]), c["clause_id"]))
    seed = int(hashlib.sha1(record.record_id.encode()).hexdigest(), 16)
    return candidates[seed % len(candidates)]


def scenario_from_denial(record: DischargeRecord, result: SubmissionResult,
                         policies: list[dict]) -> DenialScenario | None:
    """Build the Negotiator's input from a pipeline denial. None when not appealable."""
    if result.outcome not in APPEALABLE_OUTCOMES:
        return None
    policy = _policy_for(record, policies)
    if policy is None:
        return None
    clause = _pick_clause(record, policy)
    if clause is None:
        return None

    claimed = record.insurance.claimed_amount
    # A partial pays something; a rejection pays nothing. The split is deterministic so
    # the same record always yields the same scenario.
    approved = claimed // 2 if result.outcome == "partial" else 0

    return DenialScenario(
        scenario_id=f"AUTO-{record.record_id}",
        insurer_id=record.insurance.insurer_id,
        plan_id=record.insurance.plan_id,
        diagnosis=record.diagnosis_text,
        procedures=record.procedures,
        decision=InsurerDecision(
            claim_id=result.submission_id,
            insurer_id=record.insurance.insurer_id,
            plan_id=record.insurance.plan_id,
            outcome=result.outcome,
            claimed_amount=claimed,
            approved_amount=approved,
            reason_text=_REASON[result.outcome].format(
                clause_type=clause["clause_type"].replace("_", " "),
                clause_id=clause["clause_id"],
            ),
            cited_clause_id=clause["clause_id"],
        ),
    )


def make_appeal_handler(policies: list[dict], retrieve: Callable,
                        llm: Callable) -> Callable[[DischargeRecord, SubmissionResult],
                                                    AppealResult | None]:
    """The callable the orchestrator holds. Returns None when nothing is appealable.

    Note it returns the Negotiator's verdict verbatim, including `no_valid_appeal` —
    auto-raising must never pressure the agent into finding an appeal that isn't there.
    """

    def handler(record: DischargeRecord, result: SubmissionResult) -> AppealResult | None:
        scenario = scenario_from_denial(record, result, policies)
        if scenario is None:
            return None
        return draft_appeal(scenario, retrieve, llm)

    return handler
