# ClaimGuard Phase 2 — Negotiation / Appeal Agent (design)

Date: 2026-07-19
Parent: `PROJECT_SPEC.md` §6 Phase 2, §7 (Negotiator contract), §9 (edge case 12); `CLAUDE.md` prime directives 1–2.

The centerpiece. A clause-grounded appeal agent: given an insurer decision (partial approval / rejection) + the patient's policy, draft an appeal that cites specific policy clauses — or return an honest "no valid appeal" when the policy genuinely doesn't support one. **Never cite a clause it cannot ground.**

## Locked decisions
| Decision | Choice |
|---|---|
| Denial data | Dedicated denials corpus (~50 scenarios), **batch-generated deterministically from the real policy clauses** — answer keys correct by construction, no LLM in generation |
| Retrieval scope | Patient's own policy only (`insurer_id` + `plan_id`) |
| Orchestration | Standalone injectable agent + own eval; auto-appeal-on-denial deferred to a later wiring pass |
| Grounding guarantee | **Deterministic post-validation** — structured citations, filter every `clause_id` against retrieved candidates; unknown ids dropped; an "appeal" with no surviving citations becomes "no_valid_appeal". "Cites a non-corpus clause" is structurally impossible. |
| Execution | Inline TDD, ~4 merged tasks, one final whole-branch review focused on the Negotiator prompt + refusal path |
| Provider | gemini/mock as before; deterministic gate means tests prove the hard rule with no real LLM |

## New models (append to `models.py`)
- `InsurerDecision(claim_id, insurer_id, plan_id, outcome: Literal["partial","rejected"], claimed_amount: int, approved_amount: int, reason_text: str, cited_clause_id: str | None = None)`
- `DenialScenario(scenario_id, insurer_id, plan_id, diagnosis: str, procedures: list[str], decision: InsurerDecision)`
- `Citation(clause_id, quoted_text, relevance)`
- `AppealResult(scenario_id, status: Literal["appeal","no_valid_appeal"], appeal_text: str, citations: list[Citation] = [], reasoning: str = "")`
- `DenialAnswerKey(scenario_id, appeal_viable: bool, expected_clause_ids: list[str], category: str)`

## Denials corpus (`synth/denials.py` → `data/denials/`, `gen-denials` CLI)
Deterministic construction from `load_policies()`. ~50 scenarios balanced across four categories; each written as `data/denials/{scenario_id}.json` = `{"scenario": {...}, "answer_key": {...}}`. All committed (small JSON).

| Category | appeal_viable | Construction | expected_clause_ids |
|---|---|---|---|
| `partial_sublimit` | True | insurer over-applied a real `sub_limit` clause (deducted more than the clause states) | [that sub_limit clause] |
| `genuine_exclusion` | False | insurer correctly cites a real `exclusion`/`waiting_period` that applies | [] (no counter-clause) |
| `miscited_rejection` | True | insurer rejects citing a clause that does **not** apply to this claim; a real `coverage` clause does cover it | [that coverage clause] |
| `ungroundable` | False | contradictory notes / no supporting clause | [] |

Docstring states honestly: scenarios are template-constructed from clause data, so answer keys are correct by construction (clause-level verification, not per-scenario hand-check) — same honesty note as the record generator.

## Coverage retrieval (`coverage.py` → `PolicyRetriever`)
`PolicyRetriever(policies, embed_fn)` precomputes per-clause embeddings keyed by `(insurer_id, plan_id)`. `__call__(query, insurer_id, plan_id, k=5) -> list[dict]` returns that policy's clause dicts (`clause_id`, `clause_type`, `text`, `structured`), cosine-ranked, **scoped to that insurer+plan only**. Mirrors the ICD `InMemoryRetriever`; mock embed keeps tests offline.

## Negotiator (`agents/negotiator.py`)
`draft_appeal(scenario: DenialScenario, retrieve, llm=llm.complete) -> AppealResult`, reasoning tier.
1. query = `scenario.diagnosis` + decision `reason_text`; `retrieve(query, insurer_id, plan_id, k=5)` → candidates.
2. Prompt shows the decision (outcome, reason, cited_clause_id) + each candidate as `clause_id | type | text`. `json_schema` = `{status, appeal_text, citations:[{clause_id, quoted_text, relevance}], reasoning}`. System prompt = the honesty contract: cite ONLY clause_ids from the candidates; draft an appeal only when a candidate genuinely supports one; otherwise return `no_valid_appeal` and explain; never invent a clause.
3. **Deterministic gate:** `candidate_ids = {c["clause_id"] for c in candidates}`; keep only citations whose `clause_id in candidate_ids`. If `status=="appeal"` but zero citations survive → force `status="no_valid_appeal"`, clear citations, set reasoning to explain the lack of grounding.
4. Every `AppealResult` ships citations + reasoning = the explainability trace.

Hard guarantee (test-enforced): no `AppealResult` can contain a citation whose `clause_id` is outside the corpus.

## Grounding eval (`eval/grounding.py` + runner wiring)
- `grounding_rate(results, corpus_ids) -> float` — fraction of all emitted citations whose `clause_id` resolves to the corpus (the CI gate, ≥0.98; 1.0 by construction but measured to catch regressions).
- `honest_no_accuracy(results, answer_keys) -> float` — fraction where `(result.status=="appeal") == answer_key.appeal_viable`.
- `run_negotiation_eval(denials_dir, negotiator=None) -> {"n","grounding_rate","honest_no_accuracy"}`; `negotiator` is `Callable[[DenialScenario], AppealResult]` (None → all-refuse baseline). CLI `eval --negotiation` builds the real one (PolicyRetriever + llm) and prints the report.

## Edge cases + gate
- §9-2 `test_case_02_partial_approval`: partial_sublimit → status "appeal", citations include the expected sub_limit `clause_id`, all resolve.
- §9-3 `test_case_03_full_rejection`: genuine_exclusion → "no_valid_appeal", zero citations.
- §9-12 `test_case_12_ungroundable_clause` (**the key negative test**): fake llm emits a citation `clause_id="STAR-SEC1-C99"` (not in corpus) → assert it's dropped, status becomes "no_valid_appeal", zero citations.
- CI grounding gate: run the scripted/mock negotiator over `data/denials` golden → assert `grounding_rate == 1.0` (≥0.98), offline.

## Phase 2 exit criteria (from PROJECT_SPEC §6)
- [ ] Partial approval + policy → clause-cited appeal; 100% of citations resolve.
- [ ] Adversarial genuine exclusion → "no valid appeal", not a fabricated clause.
- [ ] Red-team contradictory/missing → no hallucinated citations; grounding_rate ≥0.98 gate green in CI.
- [ ] Every appeal ships an explainability trace (citations + reasoning).

## Files
Append `models.py`; new `synth/denials.py`, `agents/negotiator.py`, `eval/grounding.py`; extend `coverage.py`, `eval/runner.py`, `__main__.py` (`gen-denials`, `eval --negotiation`); `data/denials/*.json`; tests `test_denials.py`, `test_policy_retriever.py`, `test_negotiator.py`, `test_grounding.py`, edge_cases 02/03/12; update README + `docs/EVALUATION.md`.

## Out of scope
Orchestrator auto-appeal wiring · Compliance Radar (Phase 3) · patient comms (Phase 4) · frontend.
