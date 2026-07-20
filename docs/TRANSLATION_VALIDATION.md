# Translation validation — what our multilingual patient copy does and does not guarantee

**Status:** research + decision record. Written 2026-07-20, after Phase 4 shipped
patient comms in English, Hindi and Tamil.

## 1. The gap, stated precisely

`comms/messages.py` enforces a **negative** safety property: `unsafe_terms()` proves
the *absence* of known-bad phrases ("rejected", "अस्वीकार", "நிராகரி", and the rest of
the per-language blocklist). Every template is asserted against it in CI.

Warmth, register and dignity are **positive** properties. No blocklist can prove them.
A string can pass every automated check we have and still read like a government
notice to the person receiving it.

This is the same distinction the Negotiator already lives by. There, "the citation
resolves to a real clause" is provable and enforced deterministically; "the appeal is
persuasive" is not, and we never claim it. Here, "no banned term appears" is provable;
"this reads as human" is not. **Do not soften the limitation to make the feature look
finished.** The mechanism and the claim have to match.

## 2. Why the risk is higher than it looks

The translations are model-written by a non-native writer. Four failure modes, roughly
in increasing order of severity:

1. **Register drift.** Formal Hindi gravitates to *shuddh*/sarkari register.
   "आपका दावा अस्वीकृत हो गया है" is grammatically fine and emotionally wrong — it reads
   as a state rejection letter. Common Hindustani is warmer, but a non-native writer
   cannot reliably feel where that line sits.
2. **Calques.** Literal renderings of English insurance idiom ("your claim has been
   queried") can be semantically correct and either meaningless or frightening in Hindi.
   Our `claim_queried` copy is exactly the string most exposed to this.
3. **Health-literacy mismatch.** The target reader may have low literacy. Sentence
   length, word frequency and honorific choice matter more than they do in English,
   and none of them are checked today.
4. **Meaning drift — the tail risk, and the only clinical one.** Tone problems
   embarrass the author. A subtle drift in a status or medication instruction can harm
   the reader. This is why the field treats patient-facing translation as a
   *validation* problem, not a copywriting problem.

## 3. The recognised standard

WHO / ISPOR process for patient-facing materials:

independent forward translation → **independent back-translation by someone who never
saw the original** → reconciliation of discrepancies → expert panel review → cognitive
interviews with real patients.

IRBs and ethics committees routinely require back-translation for clinical materials.
Our README limitation was implicitly pointing at this standard without naming it; it
should name it.

## 4. What can be automated now — and what that is actually worth here

Four candidate gates, assessed against **this** project rather than in the abstract.

| Gate | Catches | Verdict here |
|---|---|---|
| **Back-translation + semantic equivalence check** | Meaning drift (the dangerous class) | **Do it — once, as an artifact.** See §5. |
| Second-opinion divergence (2nd model, flag disagreement) | "Which strings need a human first" | Cheap add-on to the same run; keep if it falls out for free |
| LLM-as-judge register rubric | Outlier register/reading-level failures | Screen only, never a sign-off — the judge is not native-validated either |
| Terminology alignment (NHA/Ayushman Bharat, WHO Hindi) | Vocabulary the reader already knows from real paperwork | Highest value-per-hour, needs no model at all |

### The structural caveat that changes the design

The generic advice is "add a back-translation **CI gate**", by analogy with our
grounding gate. That analogy is imperfect, and the difference decides the design:

- The grounding gate is **load-bearing on every call**, because the Negotiator
  *generates* citations at runtime from a stochastic model. New output, every time.
- Our translations are **21 static string constants**, written once. Nothing generates
  them at runtime. There is no drift channel between commits.

A permanent CI gate over constants re-proves the same fact forever and passes every
time until someone edits a string. What we actually need is a **validation run whose
output is a committed artifact**, plus a re-run trigger when the catalog changes.
That gets the entire safety benefit at a fraction of the cost and complexity.

This is the honest version of "extend the deterministic-gate philosophy to language":
extend the *philosophy* (prove what you can, document what you cannot), not the
*mechanism* shape, which was built for a different problem.

## 5. Cost analysis

Implementation options for back-translation, with real numbers:

| Approach | Setup cost | Run cost | Verdict |
|---|---|---|---|
| **Gemini via existing `llm.py`** | ~0 — `complete()` already exists | 21 strings ≈ 21 requests = the **entire** free-tier daily quota (~20 gen req/day) | Viable **once**, as a one-shot artifact run. Collides head-on with the Honest Gap eval if made recurring. |
| **IndicTrans2 locally** (AI4Bharat, ~1B params) | Multi-GB model download, torch dependency, CPU inference, Windows debugging | Free after setup, offline | **Rejected for now.** Adds a heavyweight dependency to a project whose test suite is deliberately offline, hermetic and dependency-light. Disproportionate for 21 constants. |
| Terminology alignment | Manual, no model | Free | Do first — best value per hour |

**Time estimate for the recommended slice: ~3–4 hours.** Script + one-shot run +
artifact + README wording. Compare with ~1–2 days for the IndicTrans2 route, most of
it fighting a local model install on Windows for a check that runs 21 times total.

## 6. Where this belongs in the schedule

**Inside Phase 5, not as a new phase, and not blocking it.**

Phase 5 is already scoped as "hardening, evaluation report, governance, model cards and
honest limitations." A translation-validation artifact *is* a governance document. It
sits naturally next to `docs/EVALUATION.md` and the model-card work, and it competes for
the same reviewer attention, so splitting it out would be artificial.

It does not block the other Phase 5 work (edge cases 4/7/9/10, EVALUATION.md, demo
recording) and can be done in any order relative to them.

## 7. Tiered gates — automated floor, human ceiling

**Tier 0 — now, automated (raises the floor; does not certify quality):**
- Terminology alignment against NHA/Ayushman Bharat + WHO Hindi patient materials
- One-shot back-translation of all 21 strings, semantic equivalence checked against
  source, result committed as an artifact
- Divergence flags marking which strings a human should read first
- A re-run trigger (documented, not a blocking gate) when the catalog changes

**Tier 1 — before public posting (cheap, high value):**
- One native Hindi speaker informally reading ~30 strings. Hours of effort; catches the
  worst register failures. Worth doing even at project stage.

**Tier 2 — hard product gate, before any pilot or real patient:**
- Full WHO-style process: professional forward/back-translation with reconciliation,
  clinical-communication reviewer, cognitive interviews with real patients
- Belongs on the product-conversion checklist beside the DPA, ethics sign-off,
  de-identification and clinical advisor — same class of requirement, not a nice-to-have

## 8. The line that must not be crossed

Nobody "fixes" this by swapping in machine translation and deleting the disclaimer.
That changes the mechanism while leaving the limitation exactly where it was — and
removes the honest signal that it exists. Automated gates move the floor up. Only
humans move the ceiling.

README wording, upgraded to name the standard it was implicitly citing:

> Translations are model-written and have not been validated by a native speaker or a
> clinical-communication specialist. Automated checks prove only the absence of known
> alarming terms; they cannot establish warmth, register or reading level. Real-world
> use requires WHO-style forward/back-translation validation and patient cognitive
> testing.

## References

- Back-translation in clinical materials — CSOFT Health Sciences
- Back translation in clinical trials, IRB/EC requirements
- Proportionate translation methodology in a multinational health trial (WHO/ISPOR) — PMC
- Multi-Method Validation of LLM Medical Translation — arXiv
- AI4Bharat IndicTrans2 — GitHub; IndicTrans2 paper — arXiv
