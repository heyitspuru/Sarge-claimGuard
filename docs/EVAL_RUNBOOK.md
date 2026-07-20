# Eval runbook — accumulating real-provider numbers across days

The full golden set is 200 records × 2 generate calls. The Gemini free tier allows
**exactly 20 generate requests/day** — confirmed from the provider's own quota error,
not inferred:

```
quotaId:    GenerateRequestsPerDayPerProjectPerModel-FreeTier
quotaValue: 20        model: gemini-2.5-flash
```

That is **10 records/day**, so the full 200 is a ~20-day accumulation on the free tier.
This file is the procedure, written so it can be picked up cold after a long gap.

> **Budget the day before you spend it.** The one-shot translation back-check costs ~4
> requests (2 records' worth). Run it *before* the day's eval batch, not after, or it
> will find the tank empty.

## Where the data lives

| What | Path | Committed? |
|---|---|---|
| Accumulated per-record results | `data/eval_runs/pipeline_real.jsonl` | **Yes — commit after every run** |
| Published numbers | `docs/EVALUATION.md` | Yes (written once the sample is large enough) |

The checkpoint is **append-only JSONL, one line per completed record**. It is committed
deliberately: the numbers published in `EVALUATION.md` must be traceable to the raw
per-record evidence, the same reason the golden set and denials corpus are committed.

**Commit after each daily run.** The checkpoint is the only record of days of quota
spend — losing it means starting over.

## The daily loop

Run this once per day. No Docker or Postgres needed (the eval uses the in-memory ICD
retriever, not the database).

```bash
cd ~/Desktop/claimGuard

# 1. Process as many records as today's quota allows.
#    --limit is an upper bound, not a target: it stops early and cleanly on quota.
./.venv/Scripts/python -m claimguard eval --real-run --limit 25

# 2. See where the numbers stand
./.venv/Scripts/python -m claimguard eval --real-report

# 3. Persist the day's progress
git add data/eval_runs/pipeline_real.jsonl
git commit -m "data: eval checkpoint — day N"
git push
```

`--pause N` adds a sleep between records if you hit per-minute (rather than per-day)
limits; `--pause 2` was comfortable in practice.

### What a normal ending looks like

```
completed this run : 7
total accumulated  : 10 / 200
remaining          : 190

Stopped on provider quota — this is expected on a free tier and is not
a failure. The unfinished records were left unrecorded; rerun the same
command tomorrow to resume exactly where this left off.
```

**This is success, not an error.** Records cut off by quota are deliberately left
unrecorded so tomorrow's run retries them, and they never enter the accuracy
denominator — a provider limit must never be counted as the model getting an answer
wrong.

## Prerequisites (verify once, then forget)

- `.env` has `LLM_PROVIDER=gemini` and a valid `GEMINI_API_KEY` (never committed)
- Check without printing the key:
  ```bash
  ./.venv/Scripts/python -c "from claimguard.config import get_settings; s=get_settings(); print(s.llm_provider, s.model_fast, bool(s.gemini_api_key))"
  ```
  Expect: `gemini gemini-2.5-flash True`

## Resuming after a long gap

The run is fully resumable — nothing is remembered outside the checkpoint file.

```bash
wc -l < data/eval_runs/pipeline_real.jsonl   # how many records are done
./.venv/Scripts/python -m claimguard eval --real-report
```

Then continue the daily loop. Sample size and what remains are recorded in
`docs/EVALUATION.md`.

## Reading the report

```
coding_f1            0.500     # hierarchical F1 vs the golden answer key
packaging_validity   0.700     # predicted status == expected status
pipeline errors      0

where coding lands:
  exact      3   # predicted code set matches exactly
  sibling    4   # right ICD family, wrong leaf — F1 > 0, no exact overlap
  miss       3   # no family overlap at all
  empty      -   # no codes produced
  partial    -   # some codes right, some wrong

where packaging lands (expected->actual):
  match                7
  needs_review->ready  2   # under-cautious: should have flagged for review
  ready->needs_review  1   # over-cautious: flagged a clean claim
```

`sibling` is the load-bearing distinction. A coder that lands in the right ICD family
but picks the wrong leaf is *oriented but imprecise* and needs a different fix from one
that is lost. Collapsing both into "miss" hides the most actionable finding.

Packaging direction matters for the same reason: under-cautious (a low-confidence code
reaching submission) is a **safety** failure per CLAUDE.md, while over-cautious is only
a throughput cost.

## Honest caveats to carry into EVALUATION.md

1. **Sample size.** State the achieved n against the 200 available. n≈30 is a real
   stratified sample, not a full-corpus number, and its confidence interval is wide.
2. **Ground truth is unadjudicated.** Answer keys are generated, not reviewed by
   certified coders, so coding F1 measures agreement with a synthetic key, **not
   clinical accuracy**. See `PRODUCTION_READINESS.md` §3.
3. **Closing the gap costs money, not time.** At 20 requests/day the full corpus takes
   ~20 days; enabling billing on the Gemini key would run all 200 in a single pass for
   a few dollars. Everything above is a consequence of the free tier, and that is worth
   saying plainly rather than presenting a 30-record sample as if it were the corpus.

## Related one-shot: translation back-check

Separate from the daily loop, ~4 requests, run once (and again only if patient copy
changes):

```bash
./.venv/Scripts/python -m claimguard validate-translations
git add docs/TRANSLATION_BACKCHECK.md data/translation_checked.json
git commit -m "docs: translation back-check artifact"
```

Until it runs, the four tests in `tests/test_translation_artifact.py` **skip** with an
actionable reason rather than passing vacuously.
