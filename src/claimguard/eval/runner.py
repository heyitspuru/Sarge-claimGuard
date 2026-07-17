"""Run the eval harness over a golden directory (Task 5 layout)."""

import json
from collections.abc import Callable
from pathlib import Path

from claimguard.eval.metrics import hierarchical_f1

Pipeline = Callable[[dict], dict]


def run_eval(golden_dir: Path, pipeline: Pipeline | None = None) -> dict:
    golden_dir = Path(golden_dir)
    files = sorted(golden_dir.glob("*.json"))

    f1_scores = []
    packaging_hits = 0
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        record = payload["record"]
        answer_key = payload["answer_key"]

        if pipeline is None:
            pred = {"icd_codes": [], "packaging": "ready"}
        else:
            pred = pipeline(record)

        f1_scores.append(hierarchical_f1(pred["icd_codes"], answer_key["icd_codes"]))
        if pred["packaging"] == answer_key["expected_packaging"]:
            packaging_hits += 1

    n = len(files)
    return {
        "n": n,
        "coding_f1": sum(f1_scores) / n if n else 0.0,
        "packaging_validity": packaging_hits / n if n else 0.0,
        "grounding_rate": None,
    }


def print_report(report: dict) -> None:
    print("ClaimGuard eval report")
    print("-----------------------")
    print(f"{'n records':<20} {report['n']}")
    print(f"{'coding_f1':<20} {report['coding_f1']:.3f}")
    print(f"{'packaging_validity':<20} {report['packaging_validity']:.3f}")
    grounding = report["grounding_rate"]
    print(f"{'grounding_rate':<20} {'n/a (Phase 2)' if grounding is None else f'{grounding:.3f}'}")
