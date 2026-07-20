# Demo script — 3 minutes

The recording is the artifact most people will actually judge this by, so it should show
the **one thing that makes ClaimGuard different**: an appeal that cannot cite a clause
it did not retrieve, and that says "no valid appeal" rather than inventing one.

Resist showing the pipeline first. A discharge→claim pipeline is table stakes and
nobody watches past 30 seconds of it. Open on the refusal.

**Target: 3:00.** Anything longer and the drop-off eats the ending.

---

## Setup (before recording)

```bash
cd ~/Desktop/claimGuard
docker compose up -d              # db + api
cd frontend && npm run dev        # http://localhost:5173
```

Checks: dashboard loads · patient view tab renders · terminal font large enough to read
on a phone (people watch on phones) · hide any window showing `.env`.

Recording: 1080p minimum. Keep the terminal and browser on one screen so you never
alt-tab mid-take. If you export a GIF for social, keep it under ~15MB or it won't
autoplay.

---

## Beat 1 — The problem (0:00–0:25)

Say, over the dashboard:

> "In India, a hospital discharge turns into an insurance claim, and when that claim is
> denied, most patients just… accept it. Not because the denial is right — because
> reading a policy document is a specialist skill they don't have. ClaimGuard reads it
> for them."

Don't linger. The claim is the hook, not the architecture.

## Beat 2 — The refusal, first (0:25–1:15) ⭐ the money shot

Run the negotiation eval:

```bash
python -m claimguard eval --negotiation
```

While it prints:

> "This is the part I'd want scrutinised. The agent drafts appeals grounded in the
> patient's actual policy clauses. Every citation it emits gets filtered against the
> clauses that were really retrieved — so a clause it hallucinated cannot survive into
> the output. It's structural, not a prompt asking it nicely."

Then land the point:

> "And when there's no valid appeal, it says so. That's the honest-no path. An advocate
> that argues every case is worthless; the refusals are what make the appeals credible."

On screen: `grounding_rate 1.000`.

> "Grounding rate is a hard CI gate at 0.98. If a citation ever failed to resolve, the
> build fails."

**Why this beat is first:** it is the only thing here that a competent engineer couldn't
assume you'd built. Spend the most time on it.

## Beat 3 — The loop closes (1:15–1:55)

> "That's not a separate tool you remember to open. A denial from the pipeline raises
> the appeal automatically."

Show `src/claimguard/appeal.py` briefly, or run a claim that gets denied. Point at the
audit log entry for the appeal step.

> "The claim is adjudicated, the appeal is drafted and cited, and the whole thing is in
> a replayable audit log."

## Beat 4 — Where the time goes (1:55–2:25)

Switch to the Compliance Radar tab.

> "Second question a hospital asks: where is the time actually going? IRDAI gives three
> hours from discharge to submission. The Radar shows the per-stage handoff gaps and
> flags the slowest one, with a pre-breach alert at two hours — early enough to act."

**Say the caveat out loud, don't just let the badge do it:**

> "This is a synthetic timeline — the pipeline runs in milliseconds, so there are no
> real handoff timestamps yet. It's labelled synthetic everywhere for that reason."

## Beat 5 — The patient (2:25–2:50)

Patient view tab. Switch language to हिन्दी.

> "And the patient gets told what's happening in plain language, in their language. This
> copy is template-based, deliberately not model-generated — because 'your claim was
> denied' phrased badly to someone who just left hospital is a real harm, and a reviewed
> template is auditable where a prompt isn't."

Show the pharmacy message timing:

> "Pharmacy readiness fires when the discharge is ordered, not when the insurer
> approves — so nobody waits on paperwork for their medicines."

## Beat 6 — The honest close (2:50–3:00)

> "Everything here runs on synthetic data. It's not touching a real patient record, and
> `PRODUCTION_READINESS.md` lists exactly what it would take — which is mostly not code.
> Repo's in the description."

**End on the limitation.** Counter-intuitively this is what makes people trust the rest
of it, and it is the same discipline the Negotiator runs on.

---

## Don't

- **Don't show the mock-provider eval numbers** (coding_f1 ≈ 0.06) without explaining
  they're a mechanism check. Out of context they read as "the thing doesn't work."
- **Don't imply real NHCX submission.** It's a labelled simulator; individual devs can't
  get sandbox access.
- **Don't quote coding F1 as clinical accuracy.** The answer keys are unadjudicated.
- **Don't show `.env`.** Obvious, easy to do by accident when the terminal scrolls.
- **Don't demo the frontend first.** It's the most polished part and the least
  interesting claim.

## One-liner for the post

> ClaimGuard drafts insurance appeals grounded in the patient's actual policy clauses —
> and refuses to invent one when the policy doesn't support it. Synthetic data,
> honest evals, all the limitations written down.
