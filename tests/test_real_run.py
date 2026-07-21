"""Resumability, stratification and quota-vs-quality separation for the real-eval runner.

All offline: conftest pins the mock provider, and the LLM is a local fake so the
quota path can be exercised deterministically without touching a provider.
"""

import json

import pytest

from claimguard.eval import real_run
from claimguard.eval.real_run import classify
from claimguard.icd import IcdEntry, InMemoryRetriever
from claimguard.llm import _mock_embed


def _golden(tmp_path, n=6):
    """Golden dir spanning both packaging classes and both claim types."""
    d = tmp_path / "golden"
    d.mkdir()
    combos = [("ready", "cashless"), ("rejected", "reimbursement"), ("ready", "reimbursement")]
    for i in range(n):
        expected_packaging, claim_type = combos[i % len(combos)]
        docs = (["discharge_summary", "final_bill", "preauth_form", "id_proof"]
                if expected_packaging == "ready" else ["discharge_summary"])
        payload = {
            "record": {
                "record_id": f"R{i:04d}",
                "patient": {"name": "T", "age": 30, "sex": "F", "abha_id": f"11-{i:04d}"},
                "admission_date": "2026-01-01", "discharge_date": "2026-01-03",
                "claim_type": claim_type, "specialty": "general_surgery",
                "diagnosis_text": "Acute appendicitis",
                "procedures": ["Laparoscopic appendectomy"], "medications": ["Inj X"],
                "clinical_notes": "Uneventful.", "documents": docs,
                "insurance": {"insurer_id": "INS1", "plan_id": "P1", "policy_number": "POL1",
                              "sum_insured": 500000, "claimed_amount": 80000},
            },
            "answer_key": {"record_id": f"R{i:04d}", "icd_codes": ["K35.80"],
                           "expected_packaging": expected_packaging},
        }
        (d / f"R{i:04d}.json").write_text(json.dumps(payload), encoding="utf-8")
    return d


def _retriever():
    return InMemoryRetriever([IcdEntry("K35.80", "Acute appendicitis")], _mock_embed)


def _llm_ok(prompt, *, system="", tier="fast", json_schema=None):
    if json_schema and "codes" in str(json_schema):
        return {"codes": [{"icd_code": "K35.80", "description": "Acute appendicitis",
                           "confidence": 0.9}]}
    return {
        "primary_diagnosis": "Acute appendicitis", "secondary_diagnoses": [],
        "procedures": ["Laparoscopic appendectomy"], "medications": ["Inj X"],
        "admission_course": "Uneventful.",
    }


def _llm_quota_exhausted(prompt, *, system="", tier="fast", json_schema=None):
    raise RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded for this project")


def test_run_appends_and_resumes_without_reprocessing(tmp_path):
    golden, ckpt = _golden(tmp_path), tmp_path / "ckpt.jsonl"

    first = real_run.run_incremental(golden, ckpt, limit=2, retrieve=_retriever(), llm=_llm_ok)
    assert first["completed_this_run"] == 2
    assert first["total_done"] == 2

    second = real_run.run_incremental(golden, ckpt, limit=2, retrieve=_retriever(), llm=_llm_ok)
    assert second["completed_this_run"] == 2
    assert second["total_done"] == 4

    rows = real_run.load_checkpoint(ckpt)
    assert len(rows) == 4, "resume must not reprocess records already in the checkpoint"
    assert len(set(rows)) == 4


def test_quota_stop_records_nothing_and_leaves_record_for_retry(tmp_path):
    """A 429 is the provider cutting us off, never evidence the model was wrong."""
    golden, ckpt = _golden(tmp_path), tmp_path / "ckpt.jsonl"

    summary = real_run.run_incremental(golden, ckpt, limit=3, retrieve=_retriever(),
                                       llm=_llm_quota_exhausted)
    assert summary["quota_stop"] is True
    assert summary["completed_this_run"] == 0
    assert real_run.load_checkpoint(ckpt) == {}, "quota failures must not enter the denominator"

    # tomorrow, with quota restored, the same records process normally
    recovered = real_run.run_incremental(golden, ckpt, limit=3, retrieve=_retriever(), llm=_llm_ok)
    assert recovered["completed_this_run"] == 3


def test_quota_stop_preserves_work_already_done_in_the_same_run(tmp_path):
    golden, ckpt = _golden(tmp_path), tmp_path / "ckpt.jsonl"
    real_run.run_incremental(golden, ckpt, limit=2, retrieve=_retriever(), llm=_llm_ok)

    summary = real_run.run_incremental(golden, ckpt, limit=2, retrieve=_retriever(),
                                       llm=_llm_quota_exhausted)
    assert summary["quota_stop"] is True
    assert summary["total_done"] == 2, "earlier completed records must survive a later quota stop"


def test_selection_is_stratified_not_alphabetical(tmp_path):
    """A run cut short must still span the packaging classes, not just the first files."""
    golden = _golden(tmp_path, n=6)
    picked = real_run.select_records(golden, done=set(), limit=3)
    expectations = {
        json.loads(p.read_text(encoding="utf-8"))["answer_key"]["expected_packaging"]
        for p in picked
    }
    assert expectations == {"ready", "rejected"}, "sample collapsed onto one packaging class"


def test_selection_skips_already_done(tmp_path):
    golden = _golden(tmp_path, n=6)
    picked = real_run.select_records(golden, done={"R0000", "R0001"}, limit=10)
    assert "R0000" not in [p.stem for p in picked]
    assert len(picked) == 4


def test_report_carries_failure_taxonomy(tmp_path):
    golden, ckpt = _golden(tmp_path), tmp_path / "ckpt.jsonl"
    real_run.run_incremental(golden, ckpt, limit=6, retrieve=_retriever(), llm=_llm_ok)

    report = real_run.report_from_checkpoint(ckpt)
    assert report["n"] == 6
    assert 0.0 <= report["coding_f1"] <= 1.0
    assert 0.0 <= report["packaging_validity"] <= 1.0
    # the taxonomy is the "where it fails" half PROJECT_SPEC §6 requires
    assert sum(report["coding_breakdown"].values()) == 6
    assert sum(report["packaging_breakdown"].values()) == 6


def test_empty_checkpoint_reports_zero_rather_than_crashing(tmp_path):
    report = real_run.report_from_checkpoint(tmp_path / "nothing.jsonl")
    assert report["n"] == 0
    assert report["coding_f1"] == 0.0


def test_truncated_checkpoint_line_is_tolerated(tmp_path):
    """An interrupted write must cost one record, not the whole accumulated run."""
    ckpt = tmp_path / "ckpt.jsonl"
    good = {"record_id": "R0001", "f1": 1.0, "packaging": "ready",
            "expected_packaging": "ready", "errored": False,
            "icd_codes": ["K35.80"], "expected_icd": ["K35.80"]}
    ckpt.write_text(json.dumps(good) + "\n" + '{"record_id": "R0002", "f1"', encoding="utf-8")

    rows = real_run.load_checkpoint(ckpt)
    assert list(rows) == ["R0001"]
    assert real_run.report_from_checkpoint(ckpt)["n"] == 1


def test_sibling_coding_is_not_reported_as_a_total_miss():
    """Right ICD family, wrong leaf scores >0 on hierarchical F1 and must stay visible."""
    sibling = {"icd_codes": ["K35.30"], "expected_icd": ["K35.80"], "f1": 0.5,
               "packaging": "ready", "expected_packaging": "ready", "errored": False}
    assert classify(sibling)["coding"] == "sibling"

    lost = dict(sibling, icd_codes=["Z99.9"], f1=0.0)
    assert classify(lost)["coding"] == "miss"

    exact = dict(sibling, icd_codes=["K35.80"], f1=1.0)
    assert classify(exact)["coding"] == "exact"


def test_classification_is_recomputed_not_read_from_the_checkpoint(tmp_path):
    """Accumulated runs must survive a sharpened taxonomy — facts stored, meaning derived."""
    ckpt = tmp_path / "ckpt.jsonl"
    stale = {"record_id": "R0001", "icd_codes": ["K35.30"], "expected_icd": ["K35.80"],
             "f1": 0.5, "packaging": "ready", "expected_packaging": "ready",
             "errored": False, "classification": {"coding": "OBSOLETE_LABEL"}}
    ckpt.write_text(json.dumps(stale) + "\n", encoding="utf-8")

    report = real_run.report_from_checkpoint(ckpt)
    assert "OBSOLETE_LABEL" not in report["coding_breakdown"]
    assert report["coding_breakdown"] == {"sibling": 1}


@pytest.mark.parametrize("messages,expected", [
    (["429 RESOURCE_EXHAUSTED"], True),
    (["quota exceeded"], True),
    (["KeyError: 'primary_diagnosis'"], False),
    ([], False),
])
def test_quota_detection_distinguishes_transport_from_quality(messages, expected):
    assert real_run._is_quota_error(messages) is expected


# --- the generated eval doc ---------------------------------------------------


def _report(**breakdown) -> dict:
    return {"n": 10, "coding_f1": 0.5, "packaging_validity": 0.7, "errors": 0,
            "coding_breakdown": {"exact": 5, "miss": 5},
            "packaging_breakdown": breakdown}


def test_eval_doc_calls_out_under_flagging_as_the_headline_failure(tmp_path):
    """Under- and over-flagging are NOT symmetric. Marking `ready` something the answer
    key wanted reviewed is the hard failure in CLAUDE.md; the reverse only wastes a
    reviewer's time. The doc must not average them into one 'validity' number."""
    md = real_run.evaluation_markdown(
        _report(match=7, **{"needs_review->ready": 2, "ready->needs_review": 1}),
        checkpoint=tmp_path / "cp.jsonl",
    )
    assert "2 of 10 records were under-flagged" in md
    assert "needs_review->ready" in md
    # the harmless direction must not be dressed up as the same defect
    section = md.split("### The failure that matters most")[1]
    assert "ready->needs_review" not in section


def test_eval_doc_says_so_plainly_when_nothing_is_under_flagged(tmp_path):
    md = real_run.evaluation_markdown(
        _report(match=9, **{"ready->needs_review": 1}), checkpoint=tmp_path / "cp.jsonl")
    assert "No under-flagged records" in md
    assert "under-flagged:" not in md


def test_eval_doc_is_honest_about_a_partial_sample(tmp_path):
    md = real_run.evaluation_markdown(_report(match=10), checkpoint=tmp_path / "cp.jsonl")
    assert "Partial sample" in md
    assert "n = 10 / 200" in md
    assert "Synthetic data only" in md


def test_eval_doc_handles_an_empty_checkpoint(tmp_path):
    md = real_run.evaluation_markdown(
        real_run.report_from_checkpoint(tmp_path / "none.jsonl"), checkpoint=tmp_path / "none.jsonl")
    assert "No records processed yet" in md
