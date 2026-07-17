# PROJECT_SPEC.md — Build Plan for Claude Code

### Project: **ClaimGuard** — Discharge Intelligence & Insurance *Advocacy* System

> A solo-buildable, synthetic-data, NHCX-aware engineering project whose centerpiece is a **Claims Negotiation & Appeal Agent**. Built to be *postable* first, *productizable* later.

**Strategy (locked):** Hybrid — thin discharge pipeline as plumbing; the **Negotiation Agent + Compliance Radar** are the product. **ICD-10-first, ICD-11-ready.** Synthetic data only. Ambient scribe **deferred**.

This document is written to be executed by Claude Code phase-by-phase. Each phase has **exit criteria that are tests**, not vibes. Do not advance a phase until its criteria pass.

---

## 1. Mission, non-goals, and the honesty contract

**Mission.** Give hospitals and patients an AI that (1) assembles a valid discharge claim on NHCX/FHIR rails, (2) *measures* where pre-submission time is actually lost, and (3) drafts **clause-grounded appeals** when a claim is denied or partly approved.

**Non-goals (do not build these):**
- ❌ Not an HIS/EMR replacement.
- ❌ Not a proprietary competitor to NHCX — we *consume* the standard.
- ❌ Not a "10-minute discharge" speed play — Care.fi/Aldun and IHX own that; conceded on purpose.
- ❌ Not the ambient multilingual scribe (Module B) — deferred to a post-v1 research track.
- ❌ No real patient data at project stage. Synthetic only. (DPDP exposure.)

**The honesty contract (bake into the product + README):**
- Every AI output is labeled synthetic-validated, not clinically validated, until a clinician reviews it.
- The Negotiation Agent **must refuse to cite a clause it cannot ground** in the policy corpus. A persuasive-but-ungrounded appeal is a *test failure*.
- The Compliance Radar clearly states it measures a *synthetic* journey until real timestamps exist.

---

## 2. Scope: what v1 ("the postable project") actually contains

| # | Component | In v1? | Role |
|---|---|---|---|
| A | Core discharge→claim pipeline (Summarizer, Coder, Packager, Submitter) | ✅ thin | Plumbing that produces a valid FHIR/NHCX claim from a synthetic record |
| C | **Compliance Radar** | ✅ | Timestamps every handoff; dashboard of pre-submission delay vs. IRDAI baseline |
| D | **Negotiation / Appeal Agent** | ✅ **centerpiece** | Clause-grounded appeals for partial approvals / rejections |
| E | Patient communication layer | ✅ light | Plain-language, multilingual status + SLA alerts (WhatsApp/SMS sandbox) |
| B | Multilingual ambient scribe | ❌ deferred | Post-v1 research track (see §12) |

---

## 3. Architecture (corrected from the blueprint & critique)

```
                         ┌────────────────────────────────────────┐
  Synthetic EHR / claim  │            ORCHESTRATOR (LangGraph)      │
  generator  ─────────▶  │  state machine + audit log + retries     │
                         └───┬───────┬───────┬───────┬───────┬──────┘
                             ▼       ▼       ▼       ▼       ▼
                        Summarizer  Coder  Packager Submitter Negotiator
                        (LLM,RAG)  (RAG+   (rules+  (deterministic (LLM +
                                    encoder) LLM)    FHIR client)   coverage KG-lite)
                             │       │       │        │             │
                             └───────┴───────┴────────┴─────────────┘
                                          │
                     ┌────────────────────┼─────────────────────┐
                     ▼                    ▼                     ▼
             Compliance Radar     Patient Comms Layer     Postgres + pgvector
             (timestamps→dash)    (status/SLA/WA-SMS)     (claims, audit, vectors)
```

**Key corrections baked in (vs. original blueprint and vs. the PDF's overreach):**

- **FHIR: client, not server.** Build a FHIR **R4 client** that produces/validates NHCX-shaped resources. **Do NOT stand up a full HAPI FHIR server** — you don't own that scale problem yet. (The PDF's Couchbase-vs-HAPI serialization debate is an enterprise concern; ignore at project scale.)
- **Coding: ICD-10 primary, ICD-11-ready.** The **Coder is a RAG system, not a bare classifier.** Retrieve over ICD-10 (+ optional ICD-11 map) and let an LLM assign codes with confidence + hierarchical scoring. Emit **ICD-10** because that's what NHCX/payers accept today; keep an internal ICD-11 mapping layer so switching later is a config change, not a rewrite. (Do **not** build ICD-11-first — India has no mandate.)
- **Encoder (optional, later):** if/when you add a fine-tuned encoder, use **BioClinical ModernBERT** (8,192-token, arXiv 2506.10896), **not** Bio_ClinicalBERT (512-token). For v1, RAG + an LLM is enough — don't fine-tune on day one.
- **Coverage "knowledge graph" = Postgres tables + retrieval, not Neo4j.** Model policy clauses/sub-limits/exclusions as structured rows + a vector index. Add Neo4j only if multi-hop reasoning demonstrably needs it (it won't in v1).
- **Deployment: one Docker Compose, single Indian-region VM.** No Kubernetes, no edge-cloud hybrid, no federated graph. That complexity is product-stage, not project-stage.
- **Compliance: DPDP Act 2023 + DPDP Rules 2025** (not "DISHA/PDPB"). Design consent + erasure *interfaces* now; full consent-manager integration is product-stage (deadlines: consent managers ~Nov 2026, full compliance ~May 2027).

---

## 4. Tech stack (pinned & justified)

| Layer | Choice | Why (project-stage) |
|---|---|---|
| Language / runtime | **Python 3.11** | ML/NLP ecosystem |
| Agent orchestration | **LangGraph** | Independently testable agents + explicit state machine + audit |
| LLM (reasoning) | **Claude API** — Sonnet-tier for Summarizer/Negotiator | Strong reasoning + grounding |
| LLM (fast) | **Claude API** — Haiku-tier for packaging/extraction/classification | Cost/latency control |
| Clinical coding | **RAG** over ICD-10 (pgvector) + LLM assignment; ICD-11 map optional | Emit what payers accept; avoid brittle 512-token classifier |
| FHIR | **`fhir.resources`** (Pydantic FHIR R4) as a **client**; validate against NHCX profiles | Produce valid resources without a server |
| Backend API | **FastAPI** | Fast iteration, async |
| Datastore | **PostgreSQL 16 + pgvector** | Claims, audit log, coverage clauses, vector search — one store |
| Frontend | **React + Vite + Tailwind** | Hospital dashboard, appeal review, Compliance Radar, patient view |
| Patient comms | **WhatsApp Cloud API / Twilio sandbox**; regional-language templates | Status + SLA alerts (sandbox creds only) |
| Synthetic data | **Claude API generation** + `Faker` + clinical-review checklist | Unblock everything without real EHR |
| Eval | **Custom harness** + `pytest` + a small Streamlit/React eval dashboard | Evaluation is a deliverable, not a footnote |
| Packaging | **Docker Compose** (api, db, frontend, worker) | One-command local run |
| Config/secrets | **pydantic-settings** + `.env` (never commit keys) | Clean 12-factor config |

---

## 5. Repository layout

```
claimguard/
├── README.md                  # honest project story + how to run + known failures
├── CLAUDE.md                  # operating rules for the coding agent (see separate file)
├── docker-compose.yml
├── .env.example
├── pyproject.toml
├── data/
│   ├── synthetic/             # generated records (git-ignored except a small sample)
│   ├── golden/                # hand-checked answer key (~200-500 records)
│   ├── policies/              # synthetic insurance policy corpus (clauses, sub-limits)
│   └── icd/                   # ICD-10 (+ optional ICD-11 map) reference tables
├── src/claimguard/
│   ├── orchestrator/          # LangGraph state machine + audit + retries
│   ├── agents/
│   │   ├── summarizer.py
│   │   ├── coder.py           # RAG coder (ICD-10-first)
│   │   ├── packager.py        # NHCX-schema assembly + pre-submission validation
│   │   ├── submitter.py       # deterministic FHIR client + status polling (or simulator)
│   │   └── negotiator.py      # ⭐ clause-grounded appeal agent
│   ├── fhir/                  # FHIR R4 resource builders + NHCX profile validation
│   ├── compliance_radar/      # timestamp capture + delay computation
│   ├── coverage/              # policy corpus loader + clause retrieval ("KG-lite")
│   ├── comms/                 # patient status + SLA alerts
│   ├── synth/                 # synthetic data + edge-case generators
│   ├── eval/                  # golden-set runner, metrics, hallucination/grounding checks
│   ├── api/                   # FastAPI routes
│   └── config.py
├── frontend/                  # React app (dashboard, appeal review, radar, patient view)
└── tests/
    ├── unit/
    ├── integration/
    ├── edge_cases/            # one test per §9 edge case
    └── eval/                  # accuracy + grounding gates
```

---

## 6. Phased build plan (each phase gates the next)

### Phase 0 — Foundations, data, evaluation, and a reality check *(build nothing product-y yet)*
**Do:**
1. Scaffold repo, Docker Compose (api + postgres+pgvector + frontend stub), `.env.example`, CI (`pytest` + lint).
2. **Reality check on NHCX access** — document whether an individual can get sandbox and whether *real* submission is possible. If not, commit to a **faithful FHIR/NHCX simulator** and label it as such. *(Do this before writing the Submitter.)*
3. Build the **synthetic data engine**: generate 500+ discharge records (varied specialties, lengths, cashless & reimbursement, partial-approval and rejection scenarios, code-switched free text, death-in-hospital cases). Hand-check ~200 into `data/golden/`.
4. Build a **synthetic policy corpus** (`data/policies/`): plans with clauses, sub-limits, exclusions, waiting periods — structured + prose, so the Negotiator has something real to ground against.
5. Stand up the **evaluation harness** skeleton: golden-set runner, metric stubs (coding F1 w/ hierarchical credit, grounding rate, packaging validity), CLI report.
6. Draft **DPDP-aware data model**: consent + erasure *interfaces* (even if no-op on synthetic data), full audit log.

**Exit criteria (tests):**
- [ ] `docker compose up` brings up api+db+frontend; healthchecks green.
- [ ] `make gen-data` produces ≥500 synthetic records + ≥200 golden with answer keys.
- [ ] `make eval` runs end-to-end on an empty pipeline and prints a (zero-score) report.
- [ ] `docs/NHCX_ACCESS.md` states clearly: real submission vs. simulator, with evidence.

### Phase 1 — Thin core pipeline on synthetic data (A)
**Do:** Summarizer (LLM+RAG over the record) → Coder (RAG, ICD-10-first, confidence + low-confidence flagging) → Packager (rules + LLM, NHCX-schema validation, missing-field detection) → Submitter (deterministic FHIR client or simulator, idempotent, status polling) → Orchestrator (LangGraph, retries, full audit log).

**Exit criteria (tests):**
- [ ] A synthetic record flows order→valid NHCX-shaped submission, fully logged/auditable.
- [ ] Packager **rejects** malformed/missing-document claims *before* submission (edge-case test passes).
- [ ] Coder emits ICD-10 with confidence; low-confidence items are flagged, never silently sent.
- [ ] Coding accuracy on golden set reported with **hierarchical credit** (exact-match will be low — that's expected and documented).

### Phase 2 — ⭐ Negotiation / Appeal Agent (D) — the centerpiece
**Do:** Coverage retrieval over the policy corpus → given a (partial-approval | rejection | query) + the claim, draft an appeal that **cites specific clauses**. Hard guardrail: **every citation must resolve to a real clause id or the output is rejected**. Provide an "honest no": when no valid appeal exists, say so and explain why.

**Exit criteria (tests):**
- [ ] Given a partial approval + policy, produces a clause-cited appeal; **100% of citations resolve** to the corpus (grounding test).
- [ ] Adversarial test: when the policy genuinely excludes the item, the agent returns "no valid appeal," **not** a fabricated clause.
- [ ] Red-team: contradictory notes / missing clauses → no hallucinated citations (grounding rate gate in CI, e.g. ≥0.98).
- [ ] Every appeal ships with an explainability trace (which clauses, why).

### Phase 3 — Compliance Radar (C)
**Do:** Capture timestamps at every handoff (order→summary→code→package→submit→decision); compute pre-submission delay; dashboard comparing it to the IRDAI baseline (1h pre-auth / 3h discharge). Fire **pre-breach** alerts at ~2h.

**Exit criteria (tests):**
- [ ] For a synthetic journey, radar shows exactly where time was lost.
- [ ] Pre-breach alert fires before the simulated 3h mark (edge-case test).
- [ ] Dashboard clearly labels data as synthetic.

### Phase 4 — Patient communication layer (E, light)
**Do:** Plain-language status + ETA via WhatsApp/SMS sandbox, patient's chosen language, human-safe phrasing of bad news; simple patient-facing "what's happening / what's next" view; pharmacy-readiness trigger at *order* time (not approval).

**Exit criteria (tests):**
- [ ] Test journey delivers multilingual status updates; SLA + pharmacy triggers fire at correct moments.
- [ ] "Claim queried" is phrased safely, not alarmingly (snapshot test on copy).

### Phase 5 — Hardening, evaluation report, governance, and the "post" package
**Do:** Full eval report vs. golden set (coding accuracy, grounding rate, packaging validity, **and where it fails**); explainability/citation traces everywhere; security + de-identification pass; model cards + honest limitations; polished README + short demo (video/GIF) for posting.

**Exit criteria (tests):**
- [ ] `docs/EVALUATION.md` published with real numbers **including failure modes**.
- [ ] All §9 edge-case tests green in CI.
- [ ] README tells the honest story and shows how to run + reproduce eval.
- [ ] A recorded demo exists (this is what actually gets attention when posted).

---

## 7. Agent specifications (contracts)

| Agent | Model tier | Input → Output | Hard rules |
|---|---|---|---|
| **Summarizer** | Sonnet-tier + RAG | patient record → structured discharge summary | No invented facts; cite source fields |
| **Coder** | RAG + Haiku/Sonnet | summary → ICD-10 codes + confidence | Low-confidence → human-review flag; hierarchical scoring |
| **Packager** | Haiku-tier + rules | summary+codes → NHCX claim package | Reject on missing/invalid fields *pre-submission* |
| **Submitter** | Deterministic (no LLM) | package → submission + status | Idempotent, retryable; simulator if real access blocked |
| **Negotiator** ⭐ | Sonnet-tier + coverage retrieval | decision+claim+policy → clause-cited appeal | **Never cite an ungroundable clause**; "honest no" allowed |
| Compliance Radar | Deterministic | timestamps → delay + alerts | Label synthetic; pre-breach alerting |

---

## 8. Data & synthetic-generation plan

- **Discharge records:** LLM-generated across specialties, stay lengths, languages (incl. code-switched free text), and both cashless & reimbursement. Inject the edge cases from §9 deliberately.
- **Golden set:** ~200 hand-checked records with correct codes + expected packaging outcome. This is your answer key — treat it as source of truth.
- **Policy corpus:** synthetic insurers × plans with clauses, sub-limits, exclusions, waiting periods — structured rows + prose text so the Negotiator can retrieve *and* quote.
- **Edge-case generator:** a function per §9 case so tests are reproducible.
- **(Product-stage only):** real data requires DPA + ethics sign-off + de-identification (NER-based) + consent-manager integration. Not in v1.

---

## 9. Edge-case catalog → each becomes a test in `tests/edge_cases/`

1. Cashless vs. reimbursement (two distinct paths).
2. Partial approval → appeal flow.
3. Full rejection with clause reason → grounded rebuttal or honest "no."
4. Death-in-hospital → separate expedited/compassionate workflow.
5. Missing/misnamed document → caught pre-submission.
6. Low-confidence code → flagged, never auto-submitted.
7. Consent withdrawal mid-process → stop + honor erasure interface.
8. Code-switch / regional language in inputs.
9. Offline / dropped network → graceful degradation, no data loss.
10. ABHA identity linkage + duplicate/fraud flag.
11. SLA pre-breach alert (~2h before 3h breach).
12. **Ungroundable clause** → Negotiator refuses to fabricate. *(The single most important negative test.)*

---

## 10. Testing & evaluation strategy

- **Unit:** every agent's pure logic (FHIR builders, rules, retrieval).
- **Integration:** full order→submission on synthetic records.
- **Edge cases:** one test per §9 item; all must be green to ship.
- **Eval gates in CI:** coding F1 (hierarchical) reported; **grounding rate ≥ 0.98** for Negotiator (hard gate); packaging validity = 100% on golden set.
- **Hallucination/grounding harness:** resolve every citation to a clause id; fail on any unresolved.
- **Human-in-the-loop:** clinician reviews ~50 outputs before *any* accuracy claim leaves the repo.
- **Honest failure reporting:** `docs/EVALUATION.md` documents what breaks. This is a feature.

---

## 11. Tools, plugins, MCPs & resources Claude Code should use

**Build-time (inside Claude Code):**
- **Language/frameworks:** Python 3.11, FastAPI, LangGraph, `fhir.resources`, `pytest`, `ruff`, `pydantic-settings`; React+Vite+Tailwind.
- **Data:** PostgreSQL 16 + pgvector; `Faker`; Claude API for synthetic generation.
- **Anthropic API:** Claude (Sonnet-tier for reasoning agents, Haiku-tier for fast tasks). Use the Agent SDK / tool-use loop for the orchestrator if preferred over raw LangGraph.
- **Containers:** Docker + Docker Compose (no k8s at project stage).

**External reference data to fetch/pin in Phase 0:**
- NHCX / ABDM sandbox docs + FHIR profiles (`hcxsbx.abdm.gov.in`, NHA developer portal).
- IRDAI 2024 cashless master circular (1h pre-auth / 3h discharge) — for the Radar baseline.
- ICD-10 reference tables (WHO/CBHI India), optional ICD-10↔ICD-11 map.
- DPDP Act 2023 + DPDP Rules 2025 summaries — for the consent/erasure interface design.

**Connectors/MCPs (optional, for the workflow around the build — not the app itself):**
- **GitHub** MCP → repo, issues, PRs, CI.
- **Notion** MCP → track phases/decisions/eval results (available in this workspace).
- **Gamma** MCP → generate the "post" deck when you publish (available in this workspace).
- WhatsApp/Twilio **sandbox** credentials for the comms layer (never production PII).

**Explicitly not needed at project stage:** HAPI FHIR server, Neo4j cluster, Kubernetes, edge-cloud hybrid, Couchbase, federated knowledge graph. Adopt their *ideas*, not their *ops burden*.

---

## 12. Deferred track (post-v1): Multilingual ambient scribe (Module B)
Only after v1 ships. When you do it: use **India-specific ASR** (IndicWhisper / Vaani / Sarvam), **not** generic Whisper; evaluate with a **composite metric (CER + BERTScore + entity-F1)**, not raw WER (WER structurally over-penalizes Indian languages). Explicit, visible consent + recording indicator. Doctor sign-off is a hard gate. Treat as its own research effort with its own timeline.

---

## 13. Definition of Done for "the postable project"
- [ ] Thin pipeline (A) produces valid NHCX-shaped claims on synthetic data, fully audited.
- [ ] **Negotiation Agent (D)** drafts clause-grounded appeals with **≥0.98 grounding rate** and an honest "no valid appeal" path.
- [ ] Compliance Radar (C) visualizes pre-submission delay vs. IRDAI baseline (labeled synthetic).
- [ ] Patient comms (E) delivers safe, multilingual status + SLA/pharmacy triggers.
- [ ] All §9 edge-case tests green; `docs/EVALUATION.md` published *with failures*.
- [ ] README + demo recording ready to post.

## 14. Product-conversion checklist (only if it gains traction)
- [ ] Real hospital partner + Data Processing Agreement + ethics/IRB sign-off.
- [ ] Clinical advisor (sign-off on outputs) + data/privacy advisor (DPDP).
- [ ] DPDP consent-manager integration + automated erasure (deadlines: ~Nov 2026 / ~May 2027).
- [ ] Verified NHCX **organization** onboarding for live submission.
- [ ] De-identification pipeline (NER, Indian clinical text) before any real data.
- [ ] Reposition messaging: **advocacy + precision + transparency**, not speed.
- [ ] Team (you can't run this solo as a product).

---

**North star for Claude Code:** when in doubt, cut scope toward the **Negotiation Agent**, keep everything **honest and grounded**, and prefer a **small thing that provably works** over a big thing that merely runs.
