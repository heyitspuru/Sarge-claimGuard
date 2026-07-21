# Demo script

Two demos, for two audiences. Record whichever fits; they share the same story.

| | Length | For |
|---|---|---|
| **A · The terminal walkthrough** | ~90s | Engineers. One command, one claim, every stage. |
| **B · The full product demo** | ~4 min | Everyone. Both surfaces, real UI, the human gate. |

Both open on the same thing: **an appeal that cannot cite a clause it did not retrieve,
and that says "no valid appeal" rather than inventing one.**

Resist showing the pipeline first. A discharge→claim pipeline is table stakes and nobody
watches 30 seconds of it. Open on the refusal.

---

## Demo A — the terminal walkthrough (~90s)

One command. Runs offline on the mock, so it is free, deterministic, and safe to re-run
mid-recording without spending quota.

```bash
python -m claimguard demo --record-id R0011
```

It walks one real golden record through all six stages:

1. **The agents** — live audit log from the real orchestrator: Summarizer → Coder →
   Packager → Submitter, with the packaging gate visible.
2. **The settlement** — claimed vs approved, and the **shortfall the patient pays**.
3. **The record timeline** — per-stage handoff gaps against the IRDAI 3h SLA.
4. **The advocacy** — the real clause the insurer applied, and the Negotiator's verdict.
5. **What the patient sees** — the actual messages, in `--language en|hi|ta`.
6. **What the hospital sees** — the queue state and the human review gate.

Then an honest close listing what it is not.

**R0011 is the record to use.** It is a real `gemini-2.5-flash` refusal, committed as a
demo seed: the Negotiator read the cataract sub-limit, checked it against every other
retrieved clause, and concluded the insurer applied it correctly. Say this out loud:

> "This is the agent declining to appeal. It read the patient's actual policy, found the
> sub-limit really does apply, and said so. An advocate that argues every case is
> worthless — the refusals are what make the appeals credible."

Two things to call out honestly while it scrolls:

- **The mock's ICD codes are a stub** and will not match the diagnosis. The demo labels
  this itself. What the section demonstrates is the wiring — agent order, retries, the
  audit trail, the packaging gate — none of which depend on the provider.
- Add `LLM_PROVIDER=gemini` to draft an appeal **live** — but budget for more than the
  two generate calls. The demo builds an ICD retriever and a policy retriever first, each
  of which embeds its whole corpus, so a live run also spends a batch of embedding calls
  before the Negotiator starts. The stored R0011 draft covers you if quota is tight, and
  on a recording day it usually is.

---

## Demo B — the full product demo (~4 min)

### Setup (before recording)

```bash
docker compose up -d              # db + api
cd frontend && npm run dev        # http://localhost:5173
```

Checks: both logins work · terminal font readable on a phone (people watch on phones) ·
**no window showing `.env`** · 1080p minimum. Keep terminal and browser on one screen so
you never alt-tab mid-take. GIF for social: under ~15MB or it won't autoplay.

### Beat 1 — The problem (0:00–0:25)

> "In India, a hospital discharge turns into an insurance claim, and when that claim is
> denied, most patients just… accept it. Not because the denial is right — because
> reading a policy document is a specialist skill they don't have. ClaimGuard reads it
> for them."

Don't linger. The claim is the hook, not the architecture.

### Beat 2 — The refusal, first (0:25–1:20) ⭐ the money shot

```bash
python -m claimguard eval --negotiation
```

> "Every citation the agent emits gets filtered against the clauses that were really
> retrieved, so a hallucinated clause cannot survive into the output. It's structural,
> not a prompt asking it nicely."

On screen: `grounding_rate 1.000`.

> "That's a hard CI gate at 0.98. If a citation ever failed to resolve, the build fails."

**Why this is first:** it's the only thing here a competent engineer couldn't assume you'd
built. Spend the most time on it.

### Beat 3 — The hospital console (1:20–2:15)

Log in at `/hospital` — `claims@demo-hospital.test` / `demo-claims-officer`.

**Work queue** first:

> "This is the queue of claims that need a person — denials and SLA breaches only.
> Nothing else is in here, because a queue that fills with noise gets ignored."

Open **R0011**. Show the clause the insurer applied, then the stored draft:

> "The Negotiator looked at this one and declined to appeal. That's the honest-no path,
> on a real record, from a real model call."

Then the gate — point at the review buttons:

> "A model-drafted letter is never sent to an insurer without a person reading it.
> Drafting is not sending."

**Worth saying:** a refusal can't be "approved to send" at all — there's no letter to
send, and the system refuses the action rather than recording a meaningless approval.

### Beat 4 — Where the time goes (2:15–2:45)

Compliance Radar tab.

> "Second question a hospital asks: where is the time actually going? IRDAI gives three
> hours from discharge to submission. The Radar shows per-stage handoff gaps, flags the
> slowest, and pre-breach alerts at two hours — early enough to act."

**Say the caveat out loud, don't let the badge do it:**

> "This is a synthetic timeline. The pipeline runs in milliseconds, so there are no real
> handoff timestamps yet. It's labelled synthetic everywhere for that reason."

### Beat 5 — The patient side (2:45–3:35)

**Sign out.** Do this on camera — it's the point.

Log in at `/patient` with an ABHA id from the corpus, then the simulated OTP.

> "Different surface, different login. The patient sees their own claim and nothing else
> — there's no record id in the URL, so there's nothing to tamper with. And they cannot
> reach the Compliance Radar at all; that's hospital operations data."

Switch to **हिन्दी**.

> "Plain language, in their language. No model generates a patient message at runtime —
> it's a fixed catalog, because 'your claim was denied' phrased badly to someone who just
> left hospital is a real harm."

Then the advocacy track:

> "They get a lead the moment the decision lands — something came back, we're on it,
> nothing is needed from you — and the full story once we've resolved it, naming the
> actual clause. Resolved-then-reported. A live feed of bad news with no resolution yet
> is anxiety, not transparency."

On R0011, land the honesty:

> "And when we can't help, we say that too — 'this term genuinely is part of your policy,
> challenging it would not be honest' — and still hand them a next step."

### Beat 6 — The honest close (3:35–4:00)

> "All synthetic data. Not touching a real patient record. `PRODUCTION_READINESS.md`
> lists exactly what real deployment needs, and most of it isn't code — it's a certified
> coder, a native Hindi speaker, and NHA onboarding no individual developer can get."

**End on the limitation.** Counter-intuitively this is what makes people trust the rest,
and it's the same discipline the Negotiator runs on.

---

## Don't

- **Don't show mock eval numbers** (`coding_f1 ≈ 0.06`) without saying they're a mechanism
  check. Out of context they read as "the thing doesn't work."
- **Don't quote coding F1 as clinical accuracy.** The answer keys are unadjudicated.
- **Don't imply real NHCX submission.** Labelled simulator; individual devs can't get
  sandbox access.
- **Don't claim the patient copy is human-reviewed.** It's model-written and back-check
  screened for meaning drift — which caught a real one. No native speaker has read it.
- **Don't show `.env`.** Easy to do by accident when the terminal scrolls.
- **Don't demo the frontend first.** Most polished part, least interesting claim.

## One-liner for the post

> ClaimGuard drafts insurance appeals grounded in the patient's actual policy clauses —
> and refuses to invent one when the policy doesn't support it. Synthetic data, honest
> evals, all the limitations written down.
