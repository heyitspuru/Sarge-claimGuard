# Authentication — design, and where the simulation stops

Two separate surfaces, each behind its own login:

| Surface | Route | Who | Sees |
|---|---|---|---|
| Hospital | `/hospital` | staff, email + password | Compliance Radar over every record |
| Patient | `/patient` | patient, ABHA id or policy number + OTP | **their own claim, and nothing else** |

## What this replaced

Before this, there was no authentication at all, and the two views were tabs in one page:

- `GET /radar/journeys` returned **every** record's id, claim type and timing — precisely
  the enumeration needed to attack the next line.
- `GET /patient/{record_id}` served any patient's status to anyone who guessed an id.
- The patient view was handed the whole hospital journey list and rendered it as a
  **record picker**, so a patient could select another patient's claim from a dropdown.
- `ConsentRegistry` existed and was tested (§9-7) but was never wired into the API — a
  patient who withdrew consent remained fully readable over HTTP.

## The design decision that matters

**`/patient/{record_id}` was replaced by `/patient/me`.** The record is derived from the
session, and there is no route anywhere that accepts a patient record id.

This is deliberately stronger than adding an ownership check. A check has to be
remembered on every route, every time, forever; an endpoint that takes no object
identifier cannot have an insecure-direct-object-reference bug at all. The bug class is
removed rather than defended against.

**The security boundary is `src/claimguard/auth/deps.py`, on the server.** The React
route guards in `RequireAuth.tsx` are UX — they decide what to render, and an attacker
never runs them. Every rule they express is enforced independently server-side.

## Sessions: opaque tokens, server-side

Not JWTs. The deciding factor is **revocation**:

- §9-7 requires that consent withdrawal stops processing. If the patient's session
  survived withdrawal, that would be a withdrawal in name only — so withdrawal revokes
  their live sessions, and the next request gets 403.
- A self-contained token cannot be revoked without a server-side denylist, which is a
  session store with worse ergonomics. Health data under DPDP makes revocation a
  requirement rather than a preference.

Consequences:

- The token carries no claims, so **there is nothing to sign** — no JWT library, no
  signing library. `secrets.token_urlsafe(32)` looked up in a store.
- It rides in an **httpOnly, SameSite=Lax** cookie, so an XSS bug cannot read it the way
  it could read a token in `localStorage`. SameSite covers CSRF on the POST routes.
- Staff passwords use stdlib `hashlib.scrypt`. **Zero new dependencies** for the whole
  auth layer.
- The Vite dev server proxies `/api` → `:8000` so the browser sees one origin, which
  keeps the cookie same-site in dev with no `SameSite=None` / Secure-over-http problem.

## The synthetic-only rule

**An identifier that is not in the demo corpus is refused.** This is enforced in
`auth/identity.py` and tested, not merely documented.

A demo that accepted a real 14-digit ABHA number would ingest real personal data from
the first curious visitor, which CLAUDE.md prime directive 3 forbids. Rejecting unknown
identifiers is what makes "synthetic data only" structural instead of aspirational.
Identifiers are **never logged and never echoed back**, including on rejection — a
rejected real ABHA id sitting in a log file is exactly the data we refused to accept.

## Where the simulation stops

**The OTP sends nothing.** There is no SMS gateway and no ABDM connection; the code is
returned in the API response and labelled simulated, so the demo is self-contained and
obviously not a real second factor.

Real ABHA authentication runs through **ABDM**, with the OTP delivered to the
Aadhaar-linked mobile, and requires registration as a **Health Information User** — the
same organisation-level gate that blocks real NHCX submission
([`NHCX_ACCESS.md`](NHCX_ACCESS.md)). An individual developer cannot obtain it.

What *is* faithfully reproduced is the **shape**: a challenge id, a short expiry, single
use, and a bounded number of attempts. Those are the properties the rest of the system is
built against, so swapping in real delivery changes one function rather than the design.

## Known gaps (see [`PRODUCTION_READINESS.md`](PRODUCTION_READINESS.md))

- **Sessions and OTP challenges are in-memory** — they die on restart and do not span
  replicas. Both sit behind a small interface so a Postgres table replaces them without
  touching callers.
- **Single tenant.** Records carry no `hospital_id`, so staff see every record. A tenancy
  boundary would be a field with one value today; it needs to exist before a second
  hospital does.
- **One seeded staff account, password in config.** Real staff accounts come from the
  hospital's identity provider. Hashing it at runtime protects nothing at rest — the
  real fix is an IdP, not a better hash.
- **No rate limiting on login attempts** beyond per-challenge OTP attempts.
- **No MFA for staff**, no password rotation, no account lockout.
