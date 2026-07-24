# Why this exists, and why each piece is the way it is

This is the reasoning behind ClaimGuard — the ideation, the decisions, the things that
went wrong, and what would have to be true for a hospital to actually use it.

`README.md` says what it does. `PROJECT_SPEC.md` says what was planned. This says
**why**, including the parts that did not go to plan.

---

## 1. The problem

In India, a hospital discharge becomes an insurance claim. When that claim comes back
denied or part-paid, the patient is handed a reason written in the language of the
policy document — a sub-limit, a waiting period, an exclusion — and asked, implicitly,
to either accept it or argue.

Most people accept it. **Not because the denial is right, but because checking whether
it is right requires reading a fifty-page policy document and knowing which clause
governs which situation.** That is a specialist skill. The gap is not information; the
document is usually available. The gap is the ability to read it adversarially.

That asymmetry is the whole problem. The insurer has people whose job is knowing the
policy. The patient has an evening and a PDF.

An LLM is unusually well suited to this specific gap — reading a long document,
locating the governing clause, and comparing it against a stated reason. It is also
unusually **dangerous** here, because a model that invents a clause produces something
that looks exactly like a legal argument and is worthless. Worse than worthless: a
patient who acts on a fabricated clause is in a worse position than one who did nothing.

So the project is defined by a constraint rather than a capability:

> **Draft appeals grounded in the patient's actual policy clauses — and refuse to
> invent one when the policy doesn't support it.**

The refusal is not a limitation of the system. It is the feature that makes the rest
of it trustworthy.

## 2. What "grounded" had to mean

The obvious approach is to instruct the model: *only cite clauses from the retrieved
context.* This does not work, and more importantly, it cannot be *proven* to work. You
end up measuring how often a prompt was obeyed.

The approach here is structural. After the model produces an appeal, every citation it
emitted is filtered against the clauses that were actually retrieved:

- A citation whose `clause_id` is not in the retrieved set is **discarded**.
- The quoted text is **replaced with the clause's real text**, not the model's
  rendering of it — a model paraphrasing a policy term while presenting it as a quote
  is its own failure mode.
- An appeal left with no surviving citation is **downgraded to `no_valid_appeal`**.

The consequence is that the model *cannot* emit an unresolvable citation, because the
gate runs after it and removes what does not resolve. The property does not depend on
the model's cooperation, the prompt's wording, or the provider. `grounding_rate` is a
hard test gate at ≥ 0.98; it currently sits at **1.000 across 48 denial scenarios**.

**An advocate that argues every case is worthless.** If the system appeals everything,
its appeals carry no information — a hospital would learn to ignore them within a week.
The refusals are what make the appeals credible, which is why an honest `no_valid_appeal`
is treated as a first-class success and not an error path.

## 3. Decisions, and what each was actually solving

| Decision | What it was solving | What was rejected, and why |
|---|---|---|
| **ICD-10 first, ICD-11 behind a flag** | ICD-10 is what NHCX and Indian payers accept *today* | ICD-11-first would be technically newer and practically unusable |
| **No LLM in the Packager or Submitter** | Submission must be deterministic, idempotent and replayable | An LLM anywhere in that path makes a retry non-identical, which for claim submission means duplicate filings |
| **A linear orchestrator, not LangGraph** | Four sequential agents with retries and an audit log | A graph framework for a straight line is machinery to maintain, not capability. Marked in-code for revisit if a negotiation *loop* ever needs it |
| **Provider behind a thin interface** | Every test runs offline on a deterministic mock | Tests that call a real model are slow, flaky, cost money, and stop being tests |
| **Postgres + pgvector, Docker Compose** | Vector search and a schema, nothing more | Neo4j, Kubernetes, a FHIR *server*, a federated graph — all explicitly banned in `CLAUDE.md`. Each would have been resume-shaped rather than problem-shaped |
| **Opaque server-side sessions, not JWT** | Consent withdrawal must kill a live session immediately | A JWT cannot be revoked without a server-side denylist — at which point you have rebuilt sessions with extra steps |
| **`/patient/me`, never `/patient/{id}`** | Eliminates IDOR *by construction* | An authorization check on `/patient/{id}` is a check someone can forget to write. No id in the path means no id to tamper with |
| **Synthetic data only** | Nothing here is safe to point at real patients | Real data would have required a DPA, DPDP compliance and ethics approval before a single line was useful |
| **Patient copy from a fixed catalog** | "Your claim was denied", phrased badly to someone who just left hospital, is a real harm | Generating patient messages at runtime makes every message an unreviewed model output |

## 4. Two product decisions that were not technical

### Resolved-then-reported

The patient could be shown their claim's status in real time. That was the first
instinct and it is wrong. A live feed of *"your claim was denied"* with no resolution
yet is not transparency — it is anxiety delivered faster.

But silence is its own harm. So the design has a deliberate seam:

1. **A lead lands with the decision** — something has come back, we are checking it
   against your policy, nothing is needed from you.
2. **The full story lands once it is resolved** — what the insurer applied, quoting the
   real clause, and what we did about it.

The gap between the two is the point. It is the window in which the patient holds
*"someone is on this"* instead of either silence or unresolved bad news.

### Drafting is not sending

An appeal is a formal communication to an insurer on someone else's behalf. A drafted
appeal therefore lands in `drafted` and goes nowhere until a staff member reads it and
approves or declines. This mirrors the rule that a low-confidence code never reaches
submission unreviewed.

A refusal cannot be approved at all — there is no letter, and recording an approval
against one would assert that an appeal was on its way when nothing exists.

## 5. How it was built

Phase-gated, with exit criteria that are tests rather than judgement calls. No phase
advanced until the previous one's tests passed.

| Phase | What shipped |
|---|---|
| **0** | Synthetic data engine, ICD/policy corpus, eval harness, and a reality check on NHCX access |
| **1** | The thin pipeline: Summarizer → Coder → Packager → Submitter, orchestrator, audit log |
| **2** | ⭐ **The Negotiation/Appeal Agent** — clause-grounded appeals, the deterministic citation gate, the honest-no path |
| **3** | Compliance Radar — where pre-submission time is lost, against the IRDAI baseline |
| **4** | Patient communication — multilingual, template-based, human-safe phrasing |
| **5** | Hardening: edge cases, real-provider eval, auth, the hospital console, CI |

The corpus is **200 golden records, 48 denial scenarios, 3 policies**, all generated
deterministically from a seed. **252 tests**, all offline.

The Phase-0 reality check mattered more than it looks. It established early that NHCX
sandbox access is institutionally closed to individuals, which meant the Submitter had
to be a *labelled simulator* rather than a half-finished integration pretending to be
real. Finding that out in Phase 0 rather than Phase 5 is the difference between an
honest design and a broken promise.

## 6. What went wrong — and why this section exists

Most project write-ups describe a straight line. This one did not run in a straight
line, and the failures are more informative than the successes. Every item here was
found and fixed in this repo.

**A test suite that was secretly making network calls.** One module-level line used the
provider-switching embedder instead of the mock. Invisible while the network was healthy.
A DNS failure turned a 15-second suite into **1403 seconds** and then broke collection
entirely. Fixed at the root — the provider is now pinned at import time — taking the
suite to **4.86s** and making it genuinely offline. *A test that reaches the network is
not a slow test; it is a test that is not testing what you think.*

**A CI run that was green while skipping the tests it existed for.** I added a Postgres
service so the schema tests would run. CI reported 6 skipped where local reported 4 —
`connect()` was failing on a missing extension, and a blanket `except Exception:
skip("postgres not reachable")` reported that as an absent database. *A passing CI that
silently skips is worse than no CI, because it reads as coverage.*

**Approving an appeal that did not exist.** The console offered "Approve to send" on any
draft in `drafted` — including one where the Negotiator had examined the claim and
declined. Clicking it stamped "approved by \<reviewer\>" on an appeal with empty text and
zero citations: the record then asserted a letter was on its way to an insurer when none
existed.

**Telling a patient we had appealed when we had not.** The advocacy state was predicted
from the *type* of clause the insurer cited, never from what the Negotiator actually
concluded. On one record the prediction said "filed" because the denial cited a
sub-limit, while the Negotiator had read that same sub-limit and correctly declined. The
patient was sent *"We have written back to your insurer on your behalf."* Both halves
were individually correct, which is why no test caught it — it was a gap *between* two
correct components. It was found by building an end-to-end demo that printed them
adjacent to each other.

**A Hindi message that changed its own meaning.** The English read *"the hospital team
will tell you when they are ready to collect"*. The Hindi back-translated to *"when to
take them"* — `दवा लेना` reads as consuming medicine, so a pickup notice became dosing
guidance. It was fluent, plausible, and wrong. Nobody would have caught it by reading
the Hindi; only a blind back-translation round-trip exposed it. Tamil had it right.

**Misdiagnosing my own system.** I inspected a stored `no_valid_appeal` and concluded it
was a mock-produced fake refusal. It was a genuine model refusal on a real record. I had
printed `appeal_text` — empty for both a real refusal and an empty completion — and not
`reasoning`, the field that actually distinguishes them. The correction is committed
alongside the original claim.

The through-line: **most of these were gaps between two individually-correct components,
and green signals concealed them.** That is the argument for end-to-end artifacts,
adversarial review of your own work, and treating a passing check as a question rather
than an answer.

## 7. What the numbers actually say

| Metric | Value | What it means |
|---|---|---|
| `grounding_rate` | **1.000** / 48 | No citation ever failed to resolve. Structural, not prompted. |
| `packaging_validity` | **1.000** / 170 | Packager isolation gate, offline. |
| `coding_f1` | **0.618** / n=17 | Real provider, small sample, accumulating |

The coding number is **underpowered and honestly reported as such**. The free tier
allows exactly 20 generate requests/day — confirmed from the provider's own quota error,
not inferred — which is ~10 records/day, making the full 200 a roughly 20-day
accumulation.

The finding that matters is not the headline F1. It is that **3 of 17 records were
under-flagged** — packaged `ready` when the answer key wanted a human to see them first.
Under- and over-flagging are not symmetric: over-flagging costs a reviewer's time,
under-flagging can send a wrong claim. It has held near 18% across two independent
batches, which makes it look like a real property of the confidence threshold rather
than a small-sample artifact. It is the open defect, stated first in `EVALUATION.md`
rather than averaged into a single validity score.

**Coding F1 is agreement with an unadjudicated synthetic answer key. It is not clinical
accuracy and must never be quoted as such.**

## 8. Could a hospital actually use this?

The mechanisms are built and tested. The licence to point them at reality is not — and
that distinction is the honest framing of the whole project.

What is genuinely transferable today:

- The **grounding gate** is structural, so it holds regardless of corpus realism. Point
  it at a real policy corpus and the property survives.
- The **human review gate**, the **audit log**, and the **consent-between-steps** checks
  are real mechanisms, not demonstrations.
- The **access control** is enforced server-side, with the patient IDOR removed by
  construction rather than by a check.

What stands in the way is mostly **not engineering** (full detail in
[`PRODUCTION_READINESS.md`](PRODUCTION_READINESS.md)):

- **NHCX submission is institutionally blocked** for individuals — it needs org-level
  NHA onboarding as a hospital, payer or TPA. Same gate for real ABHA authentication.
- **No certified coder has adjudicated the answer keys.** Clinical sign-off is a person,
  not a sprint.
- **Real patient data needs a DPA, DPDP compliance, ethics approval and measured
  de-identification** before a single record is touched.
- **The patient copy has not been read by a native Hindi or Tamil speaker.** Automated
  back-translation screens meaning drift; it cannot establish warmth, register or
  reading level.

The realistic next step is not deployment. It is a **pilot with one hospital on
retrospective, de-identified data under a DPA** — no NHCX submission, the Radar and the
Negotiator running read-only against real policy documents. That tests the single
biggest untested assumption: whether clause extraction from real, messy policy PDFs
feeds the grounding gate a *good* corpus. The gate guarantees citations resolve. It
guarantees nothing about whether the corpus was worth citing.

With those constraints satisfied, the architecture is designed to be pointed at reality
— the simulator boundaries are explicit and labelled precisely so they can be replaced
rather than unpicked.

## 9. What I would do differently

- **Build the end-to-end demo earlier.** It found a patient-facing bug in its first run
  that six months of unit tests had not, because it was the first thing to put two
  correct components side by side.
- **Distrust green.** Three times in this project a passing signal was concealing a real
  defect. The habit worth keeping is asking what a green check actually covered.
- **Generate the documents that carry numbers.** `EVALUATION.md` is generated from the
  checkpoint because a hand-maintained numbers doc drifts until it is quietly wrong. The
  README's test count drifted twice in a single day before I deleted the number.
- **Decide the honesty rules before there is pressure to bend them.** Writing down "a
  fabricated citation is a test failure, not a tuning parameter" while the system was
  still empty made every later decision easy. Deciding it under demo pressure would not
  have gone the same way.
