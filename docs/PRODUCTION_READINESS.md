# Production readiness — what stands between this and a real system

ClaimGuard runs end to end on **synthetic data only**. That is a deliberate project-stage
choice (CLAUDE.md prime directive 3), and it lets the build skip a long list of legal,
clinical and human gates that a real deployment cannot skip.

This document is that list. It exists so nobody — including a future me — mistakes a
working demo for a deployable product. Each item names **what is missing**, **what it
would take**, and **who gates it**, because most of these cannot be closed by writing
code at all.

Legend for the gate column: 🧑 human expertise · ⚖️ legal/contractual · 🏥 clinical ·
🏛️ institutional (NHA/insurer) · 💻 engineering

---

## 1. Real patient data

| Gate | Status | What it takes |
|---|---|---|
| ⚖️ Data Processing Agreement | **Absent** | DPA with each participating hospital before a single real record is touched |
| ⚖️ DPDP Act compliance | **Absent** | Lawful basis, purpose limitation, retention policy, breach notification. India's DPDP Act governs this and carries real penalties |
| ⚖️🧑 Ethics / IRB sign-off | **Absent** | Institutional ethics committee approval for the data use |
| 💻 De-identification | **Absent** | NER-based PII stripping with measured recall. A regex pass is not sufficient and should not be presented as one |
| 💻⚖️ Consent manager | **Absent** | ABDM consent-manager integration; §9-7 implements the *withdrawal* path against synthetic data, not a real consent artifact |

**Nothing in the current codebase is safe to point at real patient data.** The synthetic
generator, the golden set and every test fixture assume invented people.

## 2. NHCX / claim submission

Already documented in [`NHCX_ACCESS.md`](NHCX_ACCESS.md). Summary:

| Gate | Status | What it takes |
|---|---|---|
| 🏛️ NHCX sandbox access | **Blocked for individuals** | Org-level NHA onboarding as a hospital, payer or TPA |
| 🏛️ Production submission | **Blocked** | Above, plus payer-side integration agreements |
| 💻 NHCX FHIR profiles | **Partial** | Validation is base FHIR R4 only; NHCX-specific profile constraints are not layered on |

Every submission in this repo is **simulated and labelled as such** in audit logs and
claim records. That labelling must never be removed to make a demo look more impressive.

## 3. Clinical correctness

| Gate | Status | What it takes |
|---|---|---|
| 🏥 Clinical advisor sign-off | **Absent** | A coding professional reviewing the Coder's output and the golden answer keys |
| 🏥 Golden-set validity | **Unverified** | The answer keys are generated, not adjudicated by certified coders. Inter-rater agreement is unmeasured |
| ⚖️ ICD-10 licensing | **Unreviewed** | The 60-code subset is illustrative; full-table use has licensing terms |
| 🏥 Clinical safety case | **Absent** | A miscode has billing *and* care-record consequences; a real deployment needs a documented hazard analysis |

The eval reports coding F1 against **unadjudicated** keys. That number measures agreement
with a synthetic key, not clinical correctness, and should never be quoted as the latter.

## 4. Language and patient communication

Detail in [`TRANSLATION_VALIDATION.md`](TRANSLATION_VALIDATION.md).

| Gate | Status | What it takes |
|---|---|---|
| 💻 Meaning-drift screen | **Done** | Blind back-translation artifact + offline staleness guard |
| 🧑 Native-speaker review | **Absent** | One native Hindi/Tamil speaker reading the ~38 strings. Cheap, high value — do this during publicity polish |
| 🧑🏥 Clinical-communication review | **Absent** | A specialist reviewing how bad news is phrased, per language |
| 🧑 Patient cognitive interviews | **Absent** | WHO/ISPOR standard: real patients read the copy and explain back what they understood |
| 💻 Language coverage | **3 of 22** | English, Hindi, Tamil. India has 22 scheduled languages; each added one is a PR, by design |

Automated checks prove the **absence of alarming terms**. They cannot establish warmth,
register or reading level. Only humans move that ceiling.

## 5. Insurer policy corpus

| Gate | Status | What it takes |
|---|---|---|
| ⚖️🏛️ Real policy documents | **Absent** | Agreements with insurers, or use of publicly filed policy wordings with counsel review |
| ⚖️ Insurer naming | **Synthetic** | `STAR`/`MEDI`/`AROG` are invented codes. **Rename before the repo goes public** to remove any chance of collision with a real insurer's marks |
| 🧑 Clause-extraction accuracy | **Unmeasured** | Real policy PDFs are messy; clause segmentation quality is untested outside the synthetic corpus |

The Negotiator's grounding gate is **structurally** sound — it cannot cite a clause that
is not in the corpus. That property holds regardless of corpus realism. What is untested
is whether real-world clause extraction feeds it a *good* corpus.

## 6. Security and operations

| Gate | Status | What it takes |
|---|---|---|
| 💻 Secrets management | **`.env` only** | A real secret store; the current key handling is developer-grade |
| 💻 Access control / authn | **Absent** | There is no auth on the API at all. It is a localhost demo surface |
| 💻 Audit-log retention | **In-memory / local** | Durable, tamper-evident storage with a retention policy |
| 💻 Penetration testing | **Absent** | Required before exposing anything handling health data |
| 💻 Availability / DR | **Absent** | Single Docker Compose stack, no backup or recovery story |

## 7. Evaluation power

| Gate | Status | What it takes |
|---|---|---|
| 💻 Full-corpus real eval | **Partial** | Accumulating a stratified sample via `eval --real-run`; see `EVALUATION.md` for achieved n and what remains |
| 🧑 Adjudicated ground truth | **Absent** | See §3 — F1 against generated keys is not clinical accuracy |
| 💻 Appeal *quality* measurement | **Absent** | Grounding rate is proven; whether appeals actually persuade an insurer is unmeasured and arguably unmeasurable without real adjudication |

## 8. Compliance Radar timestamps

The Radar measures a **deterministic synthetic journey**, because the pipeline itself
runs in milliseconds and no real handoff timestamps exist. Every report carries
`synthetic=True` and the dashboard is labelled.

Real SLA monitoring requires instrumented hospital workflows emitting genuine
stage timestamps — an integration and change-management problem, not a code problem.

---

## The short version

Everything marked 💻 is work. Everything marked 🧑 🏥 ⚖️ 🏛️ is **not work** — it is
expertise, permission or a relationship, and no amount of engineering closes it. The
honest framing for this project is: *the mechanisms are built and tested against
synthetic data; the license to point them at reality is not.*
