"""Synthetic denials corpus generator (deterministic, no LLM).

Constructs insurer-decision scenarios from the REAL policy clauses in
data/policies. Each scenario's answer-key *label* follows from the constructed
insurer-reason narrative (over-application vs. genuine exclusion vs. mis-citation
vs. vague), NOT from a clinical clause-to-diagnosis match — the diagnosis is
cycled from the clinical templates for realism and is not topically bound to the
cited clause. So grounding (clause_ids resolve) is exact by construction, while
honest_no_accuracy measures the model's reading of the reason wording. Four
categories:

  partial_sublimit   -> appeal viable: insurer over-applied a real sub_limit
  genuine_exclusion  -> no valid appeal: insurer correctly cites an exclusion/
                        waiting_period that genuinely applies
  miscited_rejection -> appeal viable: insurer rejects citing a clause that does
                        NOT apply; a real coverage clause does cover the claim
  ungroundable       -> no valid appeal: no supporting clause / contradictory basis

Every scenario file is data/denials/{scenario_id}.json = {"scenario", "answer_key"}.
"""
import json
from pathlib import Path

from claimguard.coverage import load_policies
from claimguard.models import DenialAnswerKey, DenialScenario, InsurerDecision
from claimguard.synth import templates


def _first(clauses: list[dict], clause_type: str) -> dict | None:
    for c in clauses:
        if c["clause_type"] == clause_type:
            return c
    return None


def _scenarios_for_policy(policy: dict, base_i: int) -> list[tuple[DenialScenario, DenialAnswerKey]]:
    """Build a balanced set of scenarios for one policy from its real clauses."""
    ins, plan = policy["insurer_id"], policy["plan_id"]
    clauses = policy["clauses"]
    sub_limit = _first(clauses, "sub_limit")
    exclusion = _first(clauses, "exclusion") or _first(clauses, "waiting_period")
    waiting = _first(clauses, "waiting_period") or exclusion
    coverage = _first(clauses, "coverage")

    # diagnoses drawn from the clinical templates for realism
    dx = [(t["diagnosis_text"], t["procedures"]) for t in templates.TEMPLATES]

    out: list[tuple[DenialScenario, DenialAnswerKey]] = []
    i = base_i

    def add(category, diagnosis, procs, outcome, claimed, approved, reason, cited, viable, expected):
        nonlocal i
        sid = f"D{i:03d}"
        i += 1
        scen = DenialScenario(
            scenario_id=sid, insurer_id=ins, plan_id=plan,
            diagnosis=diagnosis, procedures=procs,
            decision=InsurerDecision(
                claim_id=f"CLM-{sid}", insurer_id=ins, plan_id=plan,
                outcome=outcome, claimed_amount=claimed, approved_amount=approved,
                reason_text=reason, cited_clause_id=cited,
            ),
        )
        key = DenialAnswerKey(
            scenario_id=sid, appeal_viable=viable, expected_clause_ids=expected, category=category,
        )
        out.append((scen, key))

    # 4 of each category, cycling through diagnoses -> ~16 per policy, ~48 total
    for n in range(4):
        d, p = dx[(base_i + n) % len(dx)]

        # partial_sublimit: insurer deducted as if the cap were lower than the clause states
        if sub_limit:
            cap = sub_limit["structured"].get("cap_inr_per_day", 5000)
            add("partial_sublimit", d, p, "partial", 100000, 80000,
                f"Room rent / sub-limit restricted to Rs.{cap - 2500} per day; excess of "
                f"Rs.20000 disallowed as per policy terms.",
                sub_limit["clause_id"], True, [sub_limit["clause_id"]])

        # genuine_exclusion: insurer correctly cites an exclusion/waiting that applies
        if exclusion:
            add("genuine_exclusion", d, p, "rejected", 90000, 0,
                f"Claim rejected: the condition falls within an excluded / waiting-period "
                f"category. {exclusion['text'][:80]}",
                exclusion["clause_id"], False, [])

        # miscited_rejection: insurer cites a clause that does not apply; coverage does apply
        if coverage and waiting:
            add("miscited_rejection", d, p, "rejected", 75000, 0,
                "Claim rejected citing a waiting-period restriction that does not apply to "
                "this hospitalization.",
                waiting["clause_id"], True, [coverage["clause_id"]])

        # ungroundable: vague reason, no specific clause, no supporting basis
        add("ungroundable", d, p, "rejected", 60000, 0,
            "Claim not admissible as per policy. No further details provided.",
            None, False, [])

    return out


def generate_denials(policies_dir: Path, out_dir: Path) -> int:
    policies = load_policies(policies_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for p in out_dir.glob("*.json"):
        p.unlink()

    n = 0
    for pi, policy in enumerate(policies):
        for scen, key in _scenarios_for_policy(policy, base_i=pi * 100):
            payload = {"scenario": scen.model_dump(), "answer_key": key.model_dump()}
            (out_dir / f"{scen.scenario_id}.json").write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            n += 1
    return n
