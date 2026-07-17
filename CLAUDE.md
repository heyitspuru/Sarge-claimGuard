# CLAUDE.md — Operating Guide for Building ClaimGuard

You are building **ClaimGuard**: a discharge-intelligence + insurance-**advocacy** system. Read `PROJECT_SPEC.md` for the full plan. This file is the standing set of rules for *how* to build. Follow it on every task.

## Prime directives
1. **The Negotiation/Appeal Agent is the point.** When trading off effort or scope, invest here. Everything else is supporting cast.
2. **Grounded or nothing.** Any clause/policy citation the Negotiation Agent emits **must resolve to a real clause id** in the corpus. If it can't ground a claim, it must say "no valid appeal" — never fabricate. This is a hard test gate (grounding rate ≥ 0.98), not a preference.
3. **Synthetic data only.** Never ingest, generate against, or store real patient data. If a task seems to need real data, stop and flag it — it's product-stage, not project-stage.
4. **Honest over impressive.** Prefer a small thing that provably works to a big thing that merely runs. Failures go in `docs/EVALUATION.md`, not under the rug.

## Scope guardrails (do NOT drift)
- ✅ In scope for v1: thin pipeline (A), Negotiation Agent (D), Compliance Radar (C), light patient comms (E).
- ❌ Deferred: multilingual ambient scribe (B). Do not start it until v1 ships.
- ❌ Do not add: HAPI FHIR **server**, Neo4j, Kubernetes, edge-cloud hybrid, Couchbase, federated graph. Use a FHIR **client**, Postgres+pgvector, and Docker Compose. If you think you need one of the banned items, write down why and ask first.
- **ICD-10-first, ICD-11-ready.** Emit ICD-10 (what NHCX/payers accept in India today). Keep ICD-11 mapping behind a config flag. Do not build ICD-11-first.

## Engineering conventions
- Python 3.11, `ruff` + type hints, `pytest`. FastAPI for the API. LangGraph for orchestration.
- Every agent is independently testable: pure functions where possible, model calls isolated behind a thin interface so they can be mocked in tests.
- Model tiering: Sonnet-tier for Summarizer/Negotiator, Haiku-tier for packaging/extraction/classification. Make the tier a config value.
- FHIR resources via `fhir.resources`; validate against NHCX profiles before "submission."
- Everything auditable: the orchestrator writes a full, replayable audit log for every claim.
- Secrets via `.env` (never commit). `.env.example` stays current.
- Determinism where it matters: the Submitter has **no LLM** — it's idempotent and retryable.

## Definition of done for any phase
- Exit-criteria tests in `PROJECT_SPEC.md` for that phase are green.
- New edge cases have a test in `tests/edge_cases/`.
- `make eval` still passes its gates (grounding ≥ 0.98; packaging validity = 100% on golden set).
- Docs updated (`README.md`, and `docs/EVALUATION.md` if numbers changed).

## When you finish a phase
Stop and report: what shipped, what the eval numbers are (including regressions), what you deferred, and the single most important risk in the next phase. Do not silently roll into the next phase.

## Things that are test failures (not judgment calls)
- A Negotiation Agent output that cites a clause not in the corpus.
- A low-confidence code that gets submitted without a human-review flag.
- A malformed/missing-document claim that reaches "submission" instead of being caught pre-submission.
- Any code path that would touch real patient data.
- A patient-facing message that states bad news in an alarming rather than human-safe way.

## Reality checks to do early
- Confirm in Phase 0 whether individual NHCX sandbox / real submission access is possible. If not, build a faithful **simulator** and label it as such in `docs/NHCX_ACCESS.md`. Don't promise end-to-end real submission you can't deliver.
