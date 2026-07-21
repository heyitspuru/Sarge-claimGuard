# Drafted appeals

Written by the API when a staff member clicks *Draft appeal with the Negotiator*
(`POST /claims/{record_id}/appeal`). Committed deliberately: drafting spends real
provider quota (~20 generate requests/day on the free tier), so a stored draft lets the
demo show genuine Negotiator output without anyone burning a call first.

Every draft lands in `review_state: "drafted"` and stays there until a person approves or
declines it. A model-drafted letter is never sent to an insurer unread.

## `R0011.json` — a real honest-no

Genuine `gemini-2.5-flash` output, not a fixture. The Negotiator read the insurer's
cited clause (the cataract sub-limit), checked it against every other retrieved clause,
and concluded the insurer had applied it **correctly** — so it declined to appeal and
said why.

> **Stale clause id, deliberately.** This draft quotes `STAR-SEC1-C03`. The insurers were
> renamed after it was generated (their abbreviations collided with real Indian
> insurance entities), and that clause is now `SYNTH1-PLANA-C03`. The text here is
> **left exactly as the model produced it** — editing a model's own words to tidy up a
> rename would turn a genuine artifact into a fabricated one, which is the specific
> dishonesty this file exists to guard against. It will be re-drafted against the renamed
> corpus on the next quota day, and this note removed then.

That is the property the whole project is built around, on a real record: an advocate
that argues every case is worthless, and the refusals are what make the appeals
credible. Note `status: "no_valid_appeal"` with an empty `appeal_text` and no citations,
but a full `reasoning`.

Worth knowing when reading these files: an empty `appeal_text` alone does **not** tell
you a refusal was genuine — the mock provider returns empty strings for every field.
`reasoning` is what distinguishes a real refusal from an empty completion.
