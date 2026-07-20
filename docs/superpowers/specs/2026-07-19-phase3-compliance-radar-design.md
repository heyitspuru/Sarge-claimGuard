# ClaimGuard Phase 3 — Compliance Radar (design)

Date: 2026-07-19
Parent: `PROJECT_SPEC.md` §6 Phase 3, §9 edge case 11. Executed in **auto mode** (autonomous decisions noted below), inline TDD.

Timestamps every handoff of a claim's journey, computes where pre-submission time was lost, compares it to the IRDAI SLA baseline, and fires pre-breach alerts. First React/shadcn UI. **Honest framing (baked in):** the pipeline runs in milliseconds, so journeys are a labeled **synthetic** timeline until real deployment timestamps exist — every surface says so.

## Autonomous decisions
| Decision | Choice |
|---|---|
| Timestamp source | Deterministic **synthetic journey generator** per `record_id` (hash-seeded) — realistic per-stage elapsed minutes, a mix of ok / pre-breach / breach. Matches the spec's "measures a synthetic journey until real timestamps exist." |
| Baseline | IRDAI: pre-auth SLA 60 min (cashless), discharge SLA 180 min; pre-breach alert at 120 min (before the 180 breach). |
| Scope of "delay" | Pre-submission delay = `order → submit` offset (what the hospital controls); decision is post-submit and shown but not gated. |
| Persistence | Radar computes on the fly from generated journeys; no DB write needed for the dashboard (the `handoff_timestamps` table stays the real-deployment hook). |
| Frontend | React + Vite + TypeScript + Tailwind + shadcn/ui, single data-dense dashboard page (journey list + detail), design system `design-system/claimguard/MASTER.md` (bg `#DBD7D8`, interactive `#F0225F`, Fira Sans/Fira Code). Renders against the API with bundled sample-data fallback so it builds/runs standalone. |
| Gate | Backend radar + API is the pytest-gated core; frontend deliverable verified by `npm run build` passing. |

## Backend (`src/claimguard/compliance_radar/`)
Models (append to `models.py`):
- `RadarStage(stage: str, at_minutes: int)` — offset from order (order = 0).
- `Journey(record_id, claim_type, stages: list[RadarStage])`.
- `RadarReport(record_id, claim_type, pre_submission_delay_min: int, stage_gaps: dict[str,int], slowest_stage: str, breach_status: Literal["ok","pre_breach","breach"], alert: bool, synthetic: bool = True)`.

`radar.py`:
- Constants `PREAUTH_SLA_MIN=60`, `DISCHARGE_SLA_MIN=180`, `PREBREACH_MIN=120`. Stage order `["order","summary","code","package","submit","decision"]`.
- `generate_journey(record_id, claim_type) -> Journey` — deterministic (sha1(record_id)); cumulative realistic per-stage gaps; hash bucket picks ok/pre-breach/breach so all three occur across the set.
- `analyze(journey) -> RadarReport` — `pre_submission_delay_min` = submit offset; `stage_gaps` = per-consecutive-stage durations up to submit (where time was lost); `slowest_stage` = max gap; `breach_status` = breach if delay > 180, pre_breach if ≥ 120, else ok; `alert` = status != ok.

## API (`api.py`)
- `GET /radar/journeys` → `[{record_id, claim_type, pre_submission_delay_min, breach_status, alert, synthetic}]` — generated for the golden record ids (reads `data/golden` for ids + claim_types; falls back to R0000..R0049 if absent).
- `GET /radar/journey/{record_id}` → full `Journey` + `RadarReport` (stages, gaps, slowest, baseline constants, synthetic label).
- CORS enabled for the Vite dev server.

## Frontend (`frontend/`)
Vite React-TS + Tailwind + shadcn (Card, Badge, Separator). One page:
- Header with **"SYNTHETIC DATA — not a live journey"** label (design system, `#F0225F` accent).
- Journey list (data-dense table): record_id, claim_type, delay, breach badge (green ok / amber pre_breach / red breach), alert.
- Detail panel for a selected journey: stage timeline (order→…→submit→decision), per-stage gap bars highlighting the slowest stage, delay vs the 180-min discharge SLA and 120-min pre-breach marker.
- Design tokens wired in Tailwind config + `@import` Fira fonts; DotField optional (deferred — static bg is fine for the gate).

## Edge cases + gate
- `tests/edge_cases/test_case_11_sla_pre_breach.py` (§9-11): a journey with delay in [120,180) → `breach_status=="pre_breach"`, `alert is True`, and the alert fires **before** the 180-min discharge breach; a >180 journey → "breach".
- Synthetic-label test: every RadarReport and API response carries `synthetic: True`.
- `analyze` correctness: `slowest_stage` = the true max gap; `stage_gaps` sum to the pre-submission delay.
- Phase 3 gate: full pytest green + ruff clean + `npm run build` succeeds.

## Phase 3 exit criteria (PROJECT_SPEC §6)
- [ ] For a synthetic journey, radar shows exactly where time was lost (`slowest_stage` + `stage_gaps`, rendered).
- [ ] Pre-breach alert fires before the simulated 3h mark (edge-case test).
- [ ] Dashboard clearly labels data as synthetic (label + `synthetic` field, test).

## Out of scope
Real timestamp capture from a live deployment · orchestrator auto-appeal wiring (still deferred) · patient comms (Phase 4) · DotField animation polish.
