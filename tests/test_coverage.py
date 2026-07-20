from pathlib import Path

import pytest

from claimguard import coverage

POLICIES_DIR = Path(__file__).resolve().parents[1] / "data" / "policies"

ALLOWED_TYPES = {"coverage", "exclusion", "sub_limit", "waiting_period"}


def test_load_policies_shape_and_counts():
    policies = coverage.load_policies(POLICIES_DIR)
    assert len(policies) == 3

    total_clauses = 0
    for p in policies:
        assert p["insurer_id"] and p["insurer_name"]
        assert p["plan_id"] and p["plan_name"]
        assert isinstance(p["clauses"], list)
        total_clauses += len(p["clauses"])
        for c in p["clauses"]:
            assert c["clause_type"] in ALLOWED_TYPES
            assert c["clause_id"].startswith(f"{p['insurer_id']}-{p['plan_id']}-C")
            assert c["text"]
            assert isinstance(c["structured"], dict)

    assert total_clauses >= 30


def test_clause_ids_globally_unique():
    policies = coverage.load_policies(POLICIES_DIR)
    ids = [c["clause_id"] for p in policies for c in p["clauses"]]
    assert len(ids) == len(set(ids))
    assert coverage.clause_ids(policies) == set(ids)


def test_load_policies_rejects_bad_clause_type(tmp_path: Path):
    bad_dir = tmp_path / "policies"
    bad_dir.mkdir()
    (bad_dir / "bad.json").write_text(
        """{
        "insurer_id": "TEST", "insurer_name": "Test Insurer",
        "plan_id": "P1", "plan_name": "Test Plan",
        "clauses": [{"clause_id": "TEST-P1-C01", "clause_type": "nonsense",
                     "text": "x", "structured": {}}]
        }""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        coverage.load_policies(bad_dir)


def test_load_policies_rejects_duplicate_clause_ids(tmp_path: Path):
    bad_dir = tmp_path / "policies"
    bad_dir.mkdir()
    clause = (
        '{"clause_id": "TEST-P1-C01", "clause_type": "coverage", '
        '"text": "x", "structured": {}}'
    )
    (bad_dir / "a.json").write_text(
        f'{{"insurer_id": "TEST", "insurer_name": "Test Insurer", '
        f'"plan_id": "P1", "plan_name": "Test Plan", "clauses": [{clause}]}}',
        encoding="utf-8",
    )
    (bad_dir / "b.json").write_text(
        f'{{"insurer_id": "TEST", "insurer_name": "Test Insurer", '
        f'"plan_id": "P1", "plan_name": "Test Plan", "clauses": [{clause}]}}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        coverage.load_policies(bad_dir)
