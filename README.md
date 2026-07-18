# ClaimGuard

A discharge-intelligence + insurance-**advocacy** system, built solo, on synthetic data only.
The thin discharge→claim pipeline (this repo, Phase 0+1) exists to feed the actual point of
the project: a **Negotiation/Appeal Agent** that drafts clause-grounded appeals for denied or
partially-approved claims (Phase 2, not yet built). Everything in this README describes what
is actually done, not the eventual vision — see `PROJECT_SPEC.md` for the full plan and
`CLAUDE.md` for the operating rules this repo was built under.

## The honesty contract

Quoted from `PROJECT_SPEC.md §1`, and binding on everything in this repo:

> - Every AI output is labeled synthetic-validated, not clinically validated, until a
>   clinician reviews it.
> - The Negotiation Agent **must refuse to cite a clause it cannot ground** in the policy
>   corpus. A persuasive-but-ungrounded appeal is a *test failure*.
> - The Compliance Radar clearly states it measures a *synthetic* journey until real
>   timestamps exist.

The Negotiation Agent (the clause-grounding hard gate above) is **Phase 2 — not built yet**.
Nothing in this repo submits a real insurance claim anywhere; there is no real patient data
anywhere; see [Known limitations](#known-limitations) for what "done" does and doesn't mean
right now.

## What this is

- A synthetic discharge-record generator (12 clinical templates, cashless + reimbursement,
  three scenarios: complete/ready, missing-document, vague-diagnosis).
- A 4-step claim pipeline — **Summarizer → Coder → Packager → Submitter** — orchestrated with
  retries and a full, replayable audit log (`src/claimguard/orchestrator.py`).
- An ICD-10 RAG coder over a small reference subset, with confidence-based human-review
  flagging that a low-confidence code can never bypass.
- A deterministic NHCX **simulator** for the Submitter (real NHCX access requires
  organization-level onboarding — see `docs/NHCX_ACCESS.md`).
- An eval harness (hierarchical coding F1, packaging validity, a grounding-rate slot reserved
  for Phase 2) runnable against a 200-record hand-checked golden set.

## What this is NOT

- Not a clinical decision support tool, not clinically validated, not for real patients.
- Not connected to real NHCX — the Submitter is a labeled simulator.
- Not the Negotiation Agent yet — Phase 2. This repo is the plumbing it will sit on top of.
- Not a full ICD-10 coder — a 60-code subset sized to the synthetic template universe.
- Not production-grade FHIR — base R4 validation only, no NHCX-specific profile constraints.

## Quickstart

```bash
git clone <this repo> && cd claimGuard
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
docker compose up -d          # postgres+pgvector; not required for eval/pytest below
python -m claimguard gen-data --n 500 --golden 200 --seed 7
python -m claimguard eval --pipeline
pytest
```

`LLM_PROVIDER` defaults to `mock` (see `.env.example`) — everything above runs fully offline,
deterministically, with no API key. Set `LLM_PROVIDER=gemini` and `GEMINI_API_KEY=...` to run
the same `eval --pipeline` command against the real Gemini provider instead.

## Architecture sketch

```
data/golden/*.json ──┐
                      ▼
              make_pipeline(retrieve, llm)          <- src/claimguard/eval/runner.py
                      │
                      ▼
     DischargeRecord.model_validate(record_dict)
                      │
                      ▼
  ┌───────────────────────────────────────────────────────────────┐
  │                    orchestrator.run_claim                     │
  │   Summarizer ──▶ Coder ──▶ Packager ──▶ Submitter              │
  │   (LLM, facts   (RAG over   (rules:      (deterministic,      │
  │    only)         ICD-10,     required     idempotent,         │
  │                   confidence)  docs,       NHCX simulator)     │
  │                                confidence)                     │
  │   every step: audit({record_id, step, status, detail}),        │
  │   one retry on exception, terminal ok/error always recorded    │
  └───────────────────────────────────────────────────────────────┘
                      │
                      ▼
     {"icd_codes": [...], "packaging": "ready"|"rejected"|"needs_review"}
```

- **Provider interface** (`src/claimguard/llm.py`): `complete()` / `embed()` switch on
  `LLM_PROVIDER` between a deterministic offline mock (used by every test and by default) and
  Gemini. Agents only ever see this interface, never a concrete SDK — that's what makes every
  agent mockable in isolation (`tests/test_summarizer.py`, `tests/test_coder.py`, etc.) as well
  as testable end-to-end with a scripted fake (`tests/integration/test_pipeline.py`).
- **Plain-Python orchestrator, not LangGraph** — `src/claimguard/orchestrator.py` is a linear
  step list with a `PipelineDeps` dataclass (`llm`, `retrieve`, `store`, `audit`) threaded
  through. Deliberately simple for a 4-step chain; LangGraph is reserved for when the Phase 2
  negotiation loop (retry-with-different-strategy, human-in-the-loop) actually needs a graph.
- **`make_pipeline(retrieve, llm)`** (`src/claimguard/eval/runner.py`) adapts `run_claim` to
  the eval contract: golden record dict in, `{"icd_codes", "packaging"}` out. This is the only
  new piece of glue Task 15 adds — everything else already existed.

## Phase status

| Phase | Scope | Status |
|---|---|---|
| 0 | Scaffold, synthetic data engine, ICD/policy reference data, eval harness skeleton, NHCX reality check | ✅ done |
| 1 | Thin pipeline (Summarizer→Coder→Packager→Submitter), orchestrator + audit log, integration + edge-case tests, real pipeline wired into eval, this README | ✅ done (this task) |
| 2 | Negotiation/Appeal Agent — clause-grounded appeals, grounding rate ≥ 0.98 hard gate, "honest no valid appeal" path | ⏳ pending |
| 3 | Compliance Radar — timestamp capture, pre-submission delay vs. IRDAI baseline, pre-breach alerts | ⏳ pending |
| 4 | Patient communication layer — plain-language multilingual status/SLA alerts | ⏳ pending |
| 5 | Hardening, full `docs/EVALUATION.md`, all §9 edge cases, demo recording | ⏳ pending |

## Eval numbers (mock provider)

Below is the actual, unedited output of `python -m claimguard eval --pipeline` on this branch,
against the 200-record golden set generated by `gen-data --n 500 --golden 200 --seed 7`, run
with the **mock** LLM provider (no API key, fully deterministic):

```
ClaimGuard eval report
-----------------------
n records            200
coding_f1            0.062
packaging_validity   0.300
grounding_rate       n/a (Phase 2)
```

This is honestly near-zero and **expected**, not a bug: the mock provider's `embed()` is a
deterministic SHA-256 hash of the input text, not a real semantic embedding, so the ICD
retriever cannot reliably surface the correct code for a given diagnosis, and the mock
`complete()` for the coder/summarizer returns schema-shaped placeholder values rather than a
real judgment. What Task 15 gates on is the **mechanism** — that `run_claim` executes
end-to-end against real golden records with a real retriever, produces a well-formed
`{"icd_codes", "packaging"}` prediction for every record, and that the packaging-validity gate
(missing-doc rejection, low-confidence needs-review) fires correctly — not the mock's
accuracy. Set `LLM_PROVIDER=gemini` with a real key and re-run `python -m claimguard eval
--pipeline` to get real numbers; whatever they are, they belong in a future update to this
section, labeled `gemini`, not silently overwriting the mock baseline above.

For comparison, the null baseline (`python -m claimguard eval`, no `--pipeline`, always
predicts `packaging="ready"` and no codes) scores `coding_f1=0.000`,
`packaging_validity=0.700` — higher packaging validity than the real mock pipeline, because
70% of the golden set's expected packaging actually is `"ready"`. This is exactly why
`packaging_validity` alone is not a sufficient gate and `coding_f1` matters too.

## Known limitations

- **Mock-provider eval numbers are near-zero by design** (see above) — they gate the pipeline
  mechanism, not coding accuracy. Real numbers require `LLM_PROVIDER=gemini` + a Gemini API key.
- **60-code ICD-10 subset** (`data/icd/icd10.csv`), sized to the synthetic template universe
  (12 templates), not the full WHO ICD-10 table. Swap in the full table before generalizing
  beyond the synthetic corpus.
- **The NHCX Submitter is a labeled simulator**, not a real integration. Individual developers
  cannot get end-to-end NHCX sandbox submission access without organization-level onboarding
  with NHA — see `docs/NHCX_ACCESS.md`. Nothing here has ever touched a real claims exchange.
- **6 of 200 golden records have a discharge date after today.** The generator draws
  `admission_date = today - rand(1,90)d`, `discharge_date = admission + rand(1,8)d` at
  generation time; regenerating on a later date will shift or shrink this, and it does not
  affect scoring (no test depends on date ordering), but it's a known artifact of when the
  fixed-seed golden set was generated versus when it's read.
- **Insurer/plan names are synthetic placeholders** (`STAR`/`MEDI`/`AROG` fictional codes with
  invented policy numbers, `data/policies/`) — plausible-looking but not modeled on any real
  insurer's actual product terms. Rename/regenerate before any public posting if there is a
  risk of a real insurer's name or product colliding with these.
- **FHIR validation is base R4 only** (`fhir.resources`), no NHCX-specific profile
  constraints layered on top yet (`src/claimguard/agents/packager.py`).
- **The Negotiation Agent, Compliance Radar, patient comms, and the ≥0.98 grounding-rate
  gate do not exist yet** — `grounding_rate` in every eval report above is `None` /
  `"n/a (Phase 2)"` on purpose, not a bug.

## Running the tests

```bash
pytest -v                       # full suite; tests marked `db` skip without a reachable postgres
ruff check src tests            # lint gate
```

`tests/integration/test_pipeline.py` runs `run_claim` end-to-end against three real golden
records (one each for `ready`/`rejected`/`needs_review`) with a real ICD retriever and a
scripted fake LLM, and asserts the audit trail is replayable. `tests/edge_cases/` covers §9
cases 1 (cashless vs. reimbursement), 5 (misnamed document caught pre-submission), and 6
(low-confidence code never reaches the submitter) — the remaining §9 cases land with their
respective phases (2/3/4).
