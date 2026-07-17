import random
from pathlib import Path

from faker import Faker

from claimguard.synth import generate, templates


def test_templates_shape():
    assert len(templates.TEMPLATES) >= 12
    for t in templates.TEMPLATES:
        assert t["icd_codes"] and t["diagnosis_text"] and t["notes"]


def test_make_record_deterministic_and_scenarios_covered():
    fk = Faker("en_IN")
    keys = set()
    for i in range(60):
        rec, key = generate.make_record(i, random.Random(i), fk)
        assert rec.record_id == key.record_id
        keys.add(key.expected_packaging)
    assert keys == {"ready", "rejected", "needs_review"}


def test_missing_doc_scenario_actually_missing(tmp_path: Path):
    n_syn, n_gold = generate.generate(50, seed=7, out_dir=tmp_path, golden_n=50)
    assert n_syn == 50 and n_gold == 50
    import json
    rejected = [json.loads(p.read_text()) for p in (tmp_path / "golden").glob("*.json")
                if json.loads(p.read_text())["answer_key"]["expected_packaging"] == "rejected"]
    assert rejected
    for g in rejected:
        req = templates.REQUIRED_DOCS[g["record"]["claim_type"]]
        assert not set(req) <= set(g["record"]["documents"])
