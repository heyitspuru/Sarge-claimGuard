import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not (ROOT / "data/golden").exists(), reason="run gen-data first")
def test_golden_set_size_and_keys():
    files = list((ROOT / "data/golden").glob("*.json"))
    assert len(files) >= 200
    g = json.loads(files[0].read_text())
    assert {"record", "answer_key"} <= g.keys()


def test_eval_cli_runs():
    out = subprocess.run([sys.executable, "-m", "claimguard", "eval"],
                         capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0 and "coding_f1" in out.stdout


def test_nhcx_doc_exists():
    assert (ROOT / "docs/NHCX_ACCESS.md").read_text().lower().count("simulator") >= 1
