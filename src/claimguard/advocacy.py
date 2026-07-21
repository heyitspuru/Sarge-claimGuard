"""What the patient is told about their appeal, and when.

The product decision this encodes: **resolved-then-reported, with a visible seam.**

A denial is never narrated to the patient as bad news the moment it lands — someone who
left hospital days ago should not read "your claim was rejected" alone at home. But
silence is its own harm, so the patient is given a *lead* immediately (something has come
back, we are on it, nothing is needed from you) and the *full* story once the appeal is
filed, including the actual clause it relies on.

Three properties fall out of that:

  1. **No LLM.** The patient-facing narrative needs the appeal *state* and the *real
     clause text* — both deterministic. The model only drafts the formal letter to the
     insurer, which the patient never reads verbatim. So this costs no quota and cannot
     hallucinate, consistent with every other patient-facing surface in the project.
  2. **Grounded the same way the Negotiator is.** Every clause shown to a patient is
     quoted from the policy corpus. If we cannot name a real clause, we say less rather
     than paraphrasing into something reassuring and false.
  3. **The refusal is shown too.** When the exclusion genuinely applies, the patient is
     told that plainly. An advocate that claims to be fighting when it is not is worse
     than one that never claimed to fight.

NOT modelled: the insurer's response to the appeal. The simulator has no notion of an
appeal outcome, so there is no "we won" state — inventing one would be exactly the
dishonesty the rest of the project is built to avoid.
"""

import json
from pathlib import Path

from claimguard import appeals_store
from claimguard.agents.submitter import submit
from claimguard.appeal import _pick_clause, _policy_for
from claimguard.config import get_settings
from claimguard.coverage import load_policies
from claimguard.models import ClaimPackage, DischargeRecord

# Minutes after the insurer's decision at which the appeal is filed (or declined).
# The gap is the point: it is the window in which the patient holds a "we're looking at
# it" message instead of silence.
REVIEW_WINDOW_MIN = 90

#: An insurer citing a *limit* is arguing about how much — arguable, so an appeal is
#: viable and rests on the clause that actually provides cover. An insurer citing an
#: *exclusion* or *waiting period* is arguing the claim is outside the policy at all;
#: where that genuinely applies, the honest answer is that there is no appeal.
_APPEALABLE_DENIAL_TYPES = ("sub_limit",)


def _load_record(record_id: str) -> DischargeRecord | None:
    path = Path(get_settings().data_dir) / "golden" / f"{record_id}.json"
    if not path.exists():
        return None
    try:
        return DischargeRecord.model_validate(
            json.loads(path.read_text(encoding="utf-8"))["record"])
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def _supporting_clause(policy: dict) -> dict | None:
    """The coverage clause an appeal against an over-applied limit would rest on."""
    coverage = [c for c in policy["clauses"] if c["clause_type"] == "coverage"]
    return sorted(coverage, key=lambda c: c["clause_id"])[0] if coverage else None


def outcome_for(record_id: str) -> str:
    """The insurer's decision. Deterministic — reuses the real Submitter so the patient
    view and the pipeline can never disagree about what happened."""
    return submit(ClaimPackage(record_id=record_id, status="ready"), {}).outcome


def advocacy_state(record_id: str, *, policies_dir: Path | None = None) -> dict:
    """The patient-facing advocacy story for one record.

    Returns `{"state", "cited_clause", "supporting_clause", "filed_after_min"}` where
    state is one of:
        none              — the claim was approved; there is nothing to advocate
        reviewing         — a decision came back and we are checking it against the policy
        filed             — an appeal has been sent, resting on a named real clause
        no_valid_appeal   — the exclusion genuinely applies, and we say so
    """
    empty = {"state": "none", "cited_clause": None, "supporting_clause": None,
             "filed_after_min": REVIEW_WINDOW_MIN}

    outcome = outcome_for(record_id)
    if outcome not in ("partial", "rejected"):
        return empty

    record = _load_record(record_id)
    if record is None:
        return empty

    settings = get_settings()
    policies = load_policies(policies_dir or Path(settings.data_dir) / "policies")
    policy = _policy_for(record, policies)
    if policy is None:
        return empty

    cited = _pick_clause(record, policy)
    if cited is None:
        return empty

    if cited["clause_type"] in _APPEALABLE_DENIAL_TYPES:
        supporting = _supporting_clause(policy)
        # Without a real clause to stand on there is no grounded appeal, and we will not
        # promise one — the same rule the Negotiator enforces.
        state = "filed" if supporting else "no_valid_appeal"
    else:
        supporting, state = None, "no_valid_appeal"

    # Everything above is a PREDICTION from clause types, used before the Negotiator has
    # run on this record. Once a real draft exists, its verdict outranks the prediction.
    #
    # Without this the two disagree in the worst possible direction: on R0011 the
    # prediction says "filed" because the denial cites a sub-limit, while the Negotiator
    # actually read that sub-limit and declined to appeal. The patient was then sent
    # "we have written back to your insurer on your behalf" — describing work nobody did.
    # A patient-facing claim about action taken must come from the action, not a guess.
    draft = appeals_store.get(record_id)
    if draft is not None:
        state = "filed" if draft["appeal"]["status"] == "appeal" else "no_valid_appeal"
        if state == "no_valid_appeal":
            supporting = None

    return {
        "state": state,
        "outcome": outcome,
        "cited_clause": _clause_view(cited),
        "supporting_clause": _clause_view(supporting) if supporting else None,
        "filed_after_min": REVIEW_WINDOW_MIN,
    }


def _clause_view(clause: dict) -> dict:
    """A clause as the patient sees it: the real id and the real text, plus a plain
    framing of what *kind* of rule it is.

    The framing is a fixed phrase per clause type, never a rewrite of the clause — a
    'simplified' paraphrase of a policy term is a legal statement we are not qualified
    to make, and a patient acting on our paraphrase rather than their policy would be
    our fault.
    """
    kind = {
        "sub_limit": "a cap on how much can be claimed for this item",
        "exclusion": "something the policy does not cover",
        "waiting_period": "a rule about how long cover takes to start",
        "coverage": "the part of the policy that provides cover",
    }.get(clause["clause_type"], "a policy term")
    return {
        "clause_id": clause["clause_id"],
        "clause_type": clause["clause_type"],
        "kind": kind,
        "text": clause["text"],
    }
