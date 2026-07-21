from pathlib import Path

from claimguard.eval import grounding
from claimguard.models import AppealResult, Citation, DenialAnswerKey


def test_grounding_rate_counts_only_resolving_citations():
    corpus = {"SYNTH1-PLANA-C02", "SYNTH1-PLANA-C01"}
    results = [
        AppealResult(scenario_id="D1", status="appeal", appeal_text="x",
                     citations=[Citation(clause_id="SYNTH1-PLANA-C02", quoted_text="a", relevance="b")]),
        AppealResult(scenario_id="D2", status="appeal", appeal_text="x",
                     citations=[Citation(clause_id="SYNTH1-PLANA-C99", quoted_text="a", relevance="b")]),
    ]
    assert grounding.grounding_rate(results, corpus) == 0.5


def test_grounding_rate_is_one_when_no_citations():
    results = [AppealResult(scenario_id="D1", status="no_valid_appeal", appeal_text="")]
    assert grounding.grounding_rate(results, {"X"}) == 1.0


def test_honest_no_accuracy_matches_answer_key():
    keys = {
        "D1": DenialAnswerKey(scenario_id="D1", appeal_viable=True, expected_clause_ids=["C1"], category="x"),
        "D2": DenialAnswerKey(scenario_id="D2", appeal_viable=False, expected_clause_ids=[], category="y"),
    }
    results = [
        AppealResult(scenario_id="D1", status="appeal", appeal_text="x"),          # correct
        AppealResult(scenario_id="D2", status="appeal", appeal_text="x"),          # wrong (should refuse)
    ]
    assert grounding.honest_no_accuracy(results, keys) == 0.5


def test_run_negotiation_eval_refuse_baseline_is_grounded():
    # refuse-all baseline over the real corpus: no citations -> grounding 1.0,
    # honest_no_accuracy == fraction of non-viable scenarios.
    rep = grounding.run_negotiation_eval(Path("data/denials"))
    assert rep["n"] >= 40
    assert rep["grounding_rate"] == 1.0
    assert 0.0 < rep["honest_no_accuracy"] < 1.0
