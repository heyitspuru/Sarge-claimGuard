"""Grounding eval for the Negotiator — turns the Phase 1 grounding_rate stub real.

grounding_rate  : fraction of all emitted citations whose clause_id resolves to
                  the policy corpus. The CI gate (>= 0.98). 1.0 by construction
                  given the deterministic gate in draft_appeal, but measured here
                  to catch any regression that lets an ungrounded citation through.
honest_no_accuracy : fraction of scenarios where the agent's appeal-vs-no-appeal
                     decision matches the answer key's appeal_viable.
"""
import json
from pathlib import Path

from claimguard.coverage import clause_ids, load_policies
from claimguard.models import AppealResult, DenialAnswerKey, DenialScenario


def grounding_rate(results: list[AppealResult], corpus_ids: set[str]) -> float:
    total = sum(len(r.citations) for r in results)
    if total == 0:
        return 1.0  # nothing emitted -> nothing ungrounded
    grounded = sum(1 for r in results for c in r.citations if c.clause_id in corpus_ids)
    return grounded / total


def honest_no_accuracy(results: list[AppealResult], answer_keys: dict[str, DenialAnswerKey]) -> float:
    if not results:
        return 0.0
    correct = 0
    for r in results:
        key = answer_keys.get(r.scenario_id)
        if key is not None and (r.status == "appeal") == key.appeal_viable:
            correct += 1
    return correct / len(results)


def _refuse(scenario: DenialScenario) -> AppealResult:
    return AppealResult(scenario_id=scenario.scenario_id, status="no_valid_appeal",
                        appeal_text="", citations=[], reasoning="baseline: no appeal")


def run_negotiation_eval(denials_dir: Path, negotiator=None,
                         policies_dir: Path = Path("data/policies")) -> dict:
    """negotiator: Callable[[DenialScenario], AppealResult]. None -> refuse-all baseline."""
    negotiator = negotiator or _refuse
    corpus_ids = clause_ids(load_policies(policies_dir))

    results: list[AppealResult] = []
    keys: dict[str, DenialAnswerKey] = {}
    for f in sorted(Path(denials_dir).glob("*.json")):
        g = json.loads(f.read_text(encoding="utf-8"))
        scenario = DenialScenario.model_validate(g["scenario"])
        keys[scenario.scenario_id] = DenialAnswerKey.model_validate(g["answer_key"])
        results.append(negotiator(scenario))

    return {
        "n": len(results),
        "grounding_rate": grounding_rate(results, corpus_ids),
        "honest_no_accuracy": honest_no_accuracy(results, keys),
    }


def print_negotiation_report(report: dict) -> None:
    print("ClaimGuard negotiation eval")
    print("---------------------------")
    print(f"{'n scenarios':<22} {report['n']}")
    print(f"{'grounding_rate':<22} {report['grounding_rate']:.3f}")
    print(f"{'honest_no_accuracy':<22} {report['honest_no_accuracy']:.3f}")
