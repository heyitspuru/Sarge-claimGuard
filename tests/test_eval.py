import json
from pathlib import Path

from claimguard.eval import metrics, runner


def test_code_credit_exact():
    assert metrics.code_credit("K35.9", "K35.9") == 1.0


def test_code_credit_same_category():
    assert metrics.code_credit("K35.2", "K35.9") == 0.5


def test_code_credit_no_match():
    assert metrics.code_credit("A90", "K35.9") == 0.0


def test_hierarchical_f1_empty_pred():
    assert metrics.hierarchical_f1([], ["A90"]) == 0.0


def test_hierarchical_f1_empty_true():
    assert metrics.hierarchical_f1(["A90"], []) == 0.0


def test_hierarchical_f1_perfect_match():
    assert metrics.hierarchical_f1(["A90", "K35.9"], ["A90", "K35.9"]) == 1.0


def _write_golden(tmp_path: Path, record_id: str, expected_packaging: str) -> None:
    payload = {
        "record": {"record_id": record_id},
        "answer_key": {
            "record_id": record_id,
            "icd_codes": ["A90"],
            "expected_packaging": expected_packaging,
        },
    }
    (tmp_path / f"{record_id}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_run_eval_none_pipeline(tmp_path: Path):
    _write_golden(tmp_path, "R0000", "ready")
    _write_golden(tmp_path, "R0001", "rejected")

    report = runner.run_eval(tmp_path, pipeline=None)

    assert report["n"] == 2
    assert report["coding_f1"] == 0.0
    assert report["packaging_validity"] == 0.5
    assert report["grounding_rate"] is None


def test_print_report_smoke(capsys):
    runner.print_report({"n": 2, "coding_f1": 0.0, "packaging_validity": 0.5, "grounding_rate": None})
    out = capsys.readouterr().out
    assert "2" in out
