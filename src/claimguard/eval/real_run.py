"""Resumable real-provider eval: accumulate a stratified sample across days.

The full golden set is 200 records x 2 generate calls. On a free-tier daily quota that
is not a single pass, so this runner checkpoints per record and resumes where it left
off. `runner.run_eval` averages metrics and throws per-record detail away; PROJECT_SPEC
§6 requires the eval report to say *where it fails*, so every record's outcome is
recorded here instead.

Two properties the honesty of the resulting numbers depends on:

  1. **A quota stop is not a quality failure.** A 429 that survives `llm._with_backoff`
     means the day's budget is gone, not that the model answered wrong. Those records
     are left UNRECORDED so tomorrow's run retries them, and they never touch the
     accuracy denominator.
  2. **A partial sample must not be a biased sample.** Selection is stratified over
     (expected_packaging, claim_type), so stopping early yields a smaller sample of the
     same shape rather than a run of whichever records sort first.
"""

import json
import time
from collections.abc import Callable
from pathlib import Path

from claimguard.eval.metrics import hierarchical_f1
from claimguard.llm import is_quota_error
from claimguard.models import DischargeRecord
from claimguard.orchestrator import PipelineDeps, run_claim


def _is_quota_error(messages: list[str]) -> bool:
    """Any of these audit-log error strings the provider cutting us off?"""
    return any(is_quota_error(m) for m in messages)


def load_checkpoint(path: Path) -> dict[str, dict]:
    """record_id -> row. Tolerates a truncated final line from an interrupted run."""
    path = Path(path)
    if not path.exists():
        return {}
    rows: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue  # partial write from a killed process; the record just gets retried
        rows[row["record_id"]] = row
    return rows


def _append(path: Path, row: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def select_records(golden_dir: Path, done: set[str], limit: int) -> list[Path]:
    """Stratified pick of up to `limit` not-yet-processed golden files.

    Round-robins across (expected_packaging, claim_type) strata so that a run cut short
    by quota still yields a representative sample rather than an alphabetical prefix.
    """
    strata: dict[tuple[str, str], list[Path]] = {}
    for path in sorted(Path(golden_dir).glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rid = payload["record"]["record_id"]
        if rid in done:
            continue
        key = (payload["answer_key"]["expected_packaging"], payload["record"]["claim_type"])
        strata.setdefault(key, []).append(path)

    picked: list[Path] = []
    while len(picked) < limit and any(strata.values()):
        for key in sorted(strata):
            if not strata[key]:
                continue
            picked.append(strata[key].pop(0))
            if len(picked) == limit:
                break
    return picked


def classify(row: dict) -> dict:
    """Per-record failure taxonomy — the 'where it fails' half of the eval report.

    Computed from the stored raw fields at REPORT time, never baked into the checkpoint.
    Sharpening the taxonomy must not invalidate days of accumulated runs, so the
    checkpoint holds facts and this holds the interpretation.

    The `sibling` bucket earns its own name: hierarchical F1 gives partial credit for
    codes sharing an ICD family, so "right family, wrong leaf" scores well above zero
    while sharing no exact code with the answer key. Collapsing that into `miss` would
    hide the single most actionable coding finding — a coder that is oriented but
    imprecise needs a different fix from one that is lost.
    """
    if row.get("errored"):
        return {"coding": "pipeline_error", "packaging": "pipeline_error"}
    pred, exp = set(row["icd_codes"]), set(row["expected_icd"])
    if not pred:
        coding = "empty"
    elif pred == exp:
        coding = "exact"
    elif pred & exp:
        coding = "partial"
    elif row.get("f1", 0.0) > 0:
        coding = "sibling"
    else:
        coding = "miss"
    pkg = ("match" if row["packaging"] == row["expected_packaging"]
           else f"{row['expected_packaging']}->{row['packaging']}")
    return {"coding": coding, "packaging": pkg}


def run_incremental(golden_dir: Path, checkpoint: Path, *, limit: int,
                    retrieve: Callable, llm: Callable, pause: float = 0.0) -> dict:
    """Process up to `limit` unprocessed golden records, appending to the checkpoint.

    Returns a summary of THIS run: how many landed, and whether it stopped on quota.
    Stopping on quota is a normal, successful outcome — the caller resumes tomorrow.
    """
    golden_dir, checkpoint = Path(golden_dir), Path(checkpoint)
    done = load_checkpoint(checkpoint)
    todo = select_records(golden_dir, set(done), limit)

    completed = 0
    quota_stop = False
    for path in todo:
        payload = json.loads(path.read_text(encoding="utf-8"))
        record = DischargeRecord.model_validate(payload["record"])
        answer_key = payload["answer_key"]

        events: list[dict] = []
        deps = PipelineDeps(llm=llm, retrieve=retrieve, store={}, audit=events.append)
        result = run_claim(record, deps)

        errors = [e["detail"].get("error", "") for e in events if e["status"] == "error"]
        if _is_quota_error(errors):
            # Leave this record unrecorded so the next run retries it. Recording it as
            # a failure would silently poison the accuracy numbers with provider limits.
            quota_stop = True
            break

        errored = result["final_status"] == "error"
        predicted = result["icd_codes"]
        packaging = result["packaging"] or "error"
        _append(checkpoint, {
            "record_id": record.record_id,
            "claim_type": record.claim_type,
            "icd_codes": predicted,
            "expected_icd": answer_key["icd_codes"],
            "packaging": packaging,
            "expected_packaging": answer_key["expected_packaging"],
            "f1": hierarchical_f1(predicted, answer_key["icd_codes"]),
            "errored": errored,
            "error_detail": errors[-1] if errors else None,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        completed += 1
        if pause:
            time.sleep(pause)

    total_available = len(list(golden_dir.glob("*.json")))
    return {
        "completed_this_run": completed,
        "total_done": len(done) + completed,
        "total_available": total_available,
        "remaining": total_available - (len(done) + completed),
        "quota_stop": quota_stop,
    }


def report_from_checkpoint(checkpoint: Path) -> dict:
    """Aggregate metrics plus the failure taxonomy over everything accumulated so far."""
    rows = list(load_checkpoint(Path(checkpoint)).values())
    n = len(rows)
    if not n:
        return {"n": 0, "coding_f1": 0.0, "packaging_validity": 0.0,
                "coding_breakdown": {}, "packaging_breakdown": {}, "errors": 0}

    coding_breakdown: dict[str, int] = {}
    packaging_breakdown: dict[str, int] = {}
    for row in rows:
        c = classify(row)
        coding_breakdown[c["coding"]] = coding_breakdown.get(c["coding"], 0) + 1
        packaging_breakdown[c["packaging"]] = packaging_breakdown.get(c["packaging"], 0) + 1

    return {
        "n": n,
        "coding_f1": sum(r["f1"] for r in rows) / n,
        "packaging_validity": sum(
            1 for r in rows if r["packaging"] == r["expected_packaging"]) / n,
        "coding_breakdown": dict(sorted(coding_breakdown.items())),
        "packaging_breakdown": dict(sorted(packaging_breakdown.items())),
        "errors": sum(1 for r in rows if r["errored"]),
    }


#: Packaging transitions where the pipeline flagged LESS than it should have. These are
#: not symmetric with over-flagging: CLAUDE.md makes "a low-confidence code that gets
#: submitted without a human-review flag" a hard failure, so under-flagging is a safety
#: defect while over-flagging is merely wasted reviewer time.
_UNDER_FLAGGED = ("needs_review->ready", "rejected->ready")


def evaluation_markdown(report: dict, *, checkpoint: Path) -> str:
    """Render docs/EVALUATION.md from the checkpoint.

    Generated rather than hand-written for one reason: the numbers move every daily run,
    and a hand-maintained eval doc drifts from the checkpoint until it is quietly wrong.
    The prose here is the stable part — how to read the numbers; the numbers are derived.
    """
    n = report["n"]
    total = len(list(Path("data/golden").glob("*.json"))) or 200
    lines = [
        "# Evaluation",
        "",
        "<!-- GENERATED by `python -m claimguard eval --real-report --write-doc`. -->",
        "<!-- Edit the generator in src/claimguard/eval/real_run.py, not this file. -->",
        "",
        f"Real-provider (`gemini-2.5-flash`) run over the synthetic golden set. "
        f"**n = {n} / {total} records.**",
        "",
    ]

    if not n:
        lines += ["No records processed yet. Run `python -m claimguard eval --real-run`.", ""]
        return "\n".join(lines)

    if n < total:
        lines += [
            f"> **Partial sample.** The free tier allows 20 generate requests/day, so the "
            f"corpus accumulates at ~10 records/day. Selection is stratified over "
            f"(expected_packaging, claim_type), so this is a smaller sample of the same "
            f"shape — not the first {n} records alphabetically. Numbers will move as it grows.",
            "",
        ]

    lines += [
        "## Headline numbers",
        "",
        "| metric | value |",
        "| --- | --- |",
        f"| coding F1 (hierarchical) | {report['coding_f1']:.3f} |",
        f"| packaging validity | {report['packaging_validity']:.3f} |",
        f"| pipeline errors | {report['errors']} |",
        "",
        "## Where it fails",
        "",
        "### Coding",
        "",
        "| outcome | records | meaning |",
        "| --- | --- | --- |",
    ]
    coding_meaning = {
        "exact": "predicted set == answer key",
        "partial": "at least one exact code shared, plus errors",
        "sibling": "right ICD family, wrong leaf — oriented but imprecise",
        "miss": "no overlap and no shared family",
        "empty": "the coder returned nothing",
        "pipeline_error": "the run itself failed",
    }
    for k, v in report["coding_breakdown"].items():
        lines.append(f"| `{k}` | {v} | {coding_meaning.get(k, '')} |")

    under = {k: v for k, v in report["packaging_breakdown"].items() if k in _UNDER_FLAGGED}
    lines += [
        "",
        "### Packaging (`expected->actual`)",
        "",
        "| transition | records |",
        "| --- | --- |",
    ]
    for k, v in report["packaging_breakdown"].items():
        lines.append(f"| `{k}` | {v} |")

    lines += ["", "### The failure that matters most", ""]
    if under:
        detail = ", ".join(f"`{k}` ({v})" for k, v in under.items())
        lines += [
            f"**{sum(under.values())} of {n} records were under-flagged: {detail}.**",
            "",
            "The pipeline marked these `ready` when the answer key says a human should have "
            "seen them first. CLAUDE.md treats a low-confidence code reaching submission "
            "without a review flag as a hard failure, not a tuning parameter, so this is "
            "the open defect — over-flagging in the other direction only costs reviewer "
            "time, while this direction is the one that can send a wrong claim.",
        ]
    else:
        lines += [
            "No under-flagged records in this sample — nothing was marked `ready` that the "
            "answer key wanted a human to see. This is the property to watch as n grows; "
            "it is the one failure mode CLAUDE.md treats as a hard gate.",
        ]

    lines += [
        "",
        "## Reproducing this",
        "",
        "```bash",
        "python -m claimguard eval --real-run --limit 10   # appends to the checkpoint",
        "python -m claimguard eval --real-report --write-doc  # regenerates this file",
        "```",
        "",
        f"Checkpoint: `{checkpoint.as_posix()}` (one JSON line per record, committed).",
        "",
        "## Limitations",
        "",
        "- **Synthetic data only.** Every record is generated. These numbers say the "
        "pipeline behaves correctly on a corpus we built; they say nothing about real "
        "discharge summaries, which are messier in ways synthetic data does not model.",
        "- **The insurer is simulated.** Denials come from a deterministic model of the "
        "policy, not a real payer, so appeal outcomes are not measured — only whether an "
        "appeal is grounded.",
        "- **Grounding is gated, not scored here.** Citation grounding is enforced as a "
        "hard test gate (≥0.98) in the negotiation eval, separate from this pipeline run.",
        "",
    ]
    return "\n".join(lines)


def print_real_report(report: dict) -> None:
    print("ClaimGuard real-provider eval")
    print("------------------------------")
    print(f"{'n records':<24} {report['n']}")
    if not report["n"]:
        print("(no records yet — run `eval --real-run --limit N` first)")
        return
    print(f"{'coding_f1':<24} {report['coding_f1']:.3f}")
    print(f"{'packaging_validity':<24} {report['packaging_validity']:.3f}")
    print(f"{'pipeline errors':<24} {report['errors']}")
    print("\nwhere coding lands:")
    for k, v in report["coding_breakdown"].items():
        print(f"  {k:<22} {v}")
    print("\nwhere packaging lands (expected->actual):")
    for k, v in report["packaging_breakdown"].items():
        print(f"  {k:<22} {v}")
