import json
from pathlib import Path

from claimguard.coverage import clause_ids, load_policies
from claimguard.models import DenialAnswerKey, DenialScenario
from claimguard.synth import denials


def test_generate_denials_balanced_and_grounded(tmp_path: Path):
    n = denials.generate_denials(Path("data/policies"), tmp_path)
    assert n >= 40
    files = sorted(tmp_path.glob("*.json"))
    assert len(files) == n

    corpus = clause_ids(load_policies(Path("data/policies")))
    cats = {}
    for f in files:
        g = json.loads(f.read_text(encoding="utf-8"))
        scen = DenialScenario.model_validate(g["scenario"])
        key = DenialAnswerKey.model_validate(g["answer_key"])
        assert scen.scenario_id == key.scenario_id
        cats[key.category] = cats.get(key.category, 0) + 1
        # every expected clause id (if any) must resolve to a real corpus clause
        for cid in key.expected_clause_ids:
            assert cid in corpus
        # the decision's insurer/plan matches the scenario
        assert scen.decision.insurer_id == scen.insurer_id
        # viable appeals name at least one expected clause; non-viable name none
        if key.appeal_viable:
            assert key.expected_clause_ids
        else:
            assert key.expected_clause_ids == []

    # all four categories represented
    assert {"partial_sublimit", "genuine_exclusion", "miscited_rejection", "ungroundable"} <= cats.keys()


def test_generate_is_deterministic(tmp_path: Path):
    a, b = tmp_path / "a", tmp_path / "b"
    denials.generate_denials(Path("data/policies"), a)
    denials.generate_denials(Path("data/policies"), b)
    fa = {p.name: p.read_text(encoding="utf-8") for p in a.glob("*.json")}
    fb = {p.name: p.read_text(encoding="utf-8") for p in b.glob("*.json")}
    assert fa == fb
