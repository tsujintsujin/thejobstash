# TheJobStash

Upload a resume once. Every morning the pool of scraped jobs is scored against
it and the handful worth your time is emailed over — plus the ones that came
close, and exactly what blocked them.

**Payments are switched off.** Plans are granted free on request.

---

## Why it is built this way

The single architectural decision everything else follows from: **ingestion is
separated from matching.**

```
INGESTION (once a day, user-independent)   MATCHING (per user, on demand)
ingest.py → 13 boards → jobs table         resume → profile → SQL + score
minutes, once                              sub-second, any time
```

A per-user scrape would hit RemoteOK 500 times a day for the same public data,
get the IP banned, and make every user wait minutes on a spinner. Scraping once
into a shared pool means the marginal cost of the five-hundredth subscriber is a
SQL query.

The second decision: **scoring collects blockers instead of returning early.**
`JobHunt/jobhunt.py` returns `0` the moment any gate fails, so a perfect React
role that happens to be onsite in Berlin is indistinguishable from a nursing
vacancy — both score zero. Here every posting that is plausibly your profession
gets a real score *and* a list of what stopped it, which is what makes the
"came close" section rankable.

Exactly one check still excludes outright: role family. A nursing vacancy is not
a near-miss for a developer, and padding a thin day with those is what would
genuinely make the product look lazy.

---

## Relationship to `JobHunt/`

`JobHunt/` is Justin's personal daily sweep. **It is not modified by anything
here.** It keeps its own `score()`, its own `profile.py`, its own database and
its own n8n workflow (`jobhuntdaily0001`).

| Shared | How |
|---|---|
| `JobHunt/sources.py` | imported read-only — job boards break constantly and one fix should serve both |
| `JobHunt/jobhunt.py` | **not used** — TheJobStash has its own scorer |
| `JobHunt/profile.py` | **not used** — read only by `test_matching.py`, for parity checking |
| `JobHunt/jobs.db` | **not used** — TheJobStash has `jobstash.db` |

The n8n workflow is a separate file with a **different stable id**
(`jobhuntsaas0001`). n8n keys imports on that id, so reusing the daily sweep's
would have silently overwritten it.

---

## Layout

```
profiles.py       a user as data — skills, level, geography, authorisation
matching.py       the scorer. Blockers not early returns; profile is an argument
resume_parse.py   resume file → Profile, deterministic, no API key needed
db.py             schema + helpers. Opens D1 when configured, else SQLite
d1.py             a sqlite3-shaped connection backed by Cloudflare D1
r2.py             uploads a rendered digest to R2, through the site
ingest.py         scrape every board → shared pool, dedupe, keep descriptions
delivery.py       the daily budget: target, floor, backfill, near-miss quota
render.py         digest → HTML + PDF (headless Chrome)
mailer.py         outbox/ by default, Resend when JOBSTASH_RESEND_KEY is set
run_delivery.py   the cron entrypoint the n8n workflow calls
api_bridge.py     JSON CLI, and the dispatch py_server.py serves over HTTP
py_server.py      the scorer as an HTTP service, published by a tunnel
scorer.cmd        starts py_server + cloudflared together
web/              the site (Next.js 15 on Cloudflare Workers, D1, R2)
```

## Where it runs

Live at <https://thejobstash.com>.

```
CLOUDFLARE                              THIS MACHINE
Worker (Next.js)  ──── D1 ────┐         py_server.py  (the scorer)
  pages, sessions, accounts   │           ├─ resume_parse, matching, summarise
  /api/internal/d1  ──────────┼───────────┤  render.py (headless Chrome)
  /api/internal/digest ── R2  │           └─ ingest.py + run_delivery.py (n8n)
                              └───────────── reached over a Cloudflare Tunnel
```

The split is the one the architecture always had, just drawn across two
machines: **the site owns the data, this machine owns the Python.** Workers
cannot start a process, and the scorer needs pypdf, python-docx and a headless
Chrome, so `lib/py.ts` stopped calling `spawn()` and started calling `fetch()`.
The JSON contract either side of that call did not change, which is why
`matching.py`, `delivery.py` and `render.py` were not touched at all — there is
still exactly one implementation of the scoring rules.

The tunnel dials **out**, so nothing here listens for inbound connections and
no port is forwarded. That was already the rule; it still is.

**What needs this machine up:** the free trial, resume upload, digest preview
and delivery. Everything else — pages, sign-in, the dashboard, plan changes —
is served by Cloudflare and does not care whether this machine is on. When it
is off, those four say "the scorer is offline" rather than failing obscurely.

### Running the scorer

Double-click `scorer.cmd`, or:

```bash
python py_server.py                       # localhost:3300
cloudflared tunnel run jobstash-scorer    # publishes scorer.thejobstash.com
```

Both read `.env.cloudflare`, which is local-only and never committed.

### Running the site locally

```bash
cd web
npm install
npm run dev                  # localhost:3200, Next's own dev server
npm run d1:local             # create the local database's tables (web/.localdb)
```

### Deploying

Push to `master` on GitHub. Cloudflare builds and deploys it; nothing is
deployed from this PC, and `npm run deploy` refuses. A new file in
`web/migrations/` is applied by hand in the Cloudflare dashboard's D1 console.

```bash
npm run migration:gen        # regenerate 0001_init.sql from db.py's SCHEMA
```

`db.py` stays the single source of truth for the table shape; the D1 migration
is generated from it rather than hand-maintained beside it.

### Filling the pool

```bash
python ingest.py --fast      # writes straight into D1 when configured
```

Tests:

```bash
python test_matching.py      # 55 unit checks + a run over the whole pool
python test_cloudflare.py    # 37 checks that the D1 shim matches sqlite3
python live_check.py         # scores live postings with real description text
bash e2e.sh                  # walks the real site over HTTP
```

### One thing that is not a preference

Cloudflare's Web Crypto refuses PBKDF2 above **100,000** iterations. `db.py`'s
`PBKDF2_ROUNDS` and `web/lib/db.ts`'s `ROUNDS` must therefore both be 100,000
and must stay equal: a password set by one side is verified by the other, and a
mismatch does not look like a bug, it looks like everyone typing the wrong
password. `test_cloudflare.py` asserts the two agree.

## The delivery budget

From the numbers in JobHunt's own database: a cold start finds ~75 matches for a
narrow profile, then the daily rate settles at 8–13. Sent raw that reads as a
cliff, and a cliff reads as "the app broke". The pool is not running out — day
one was a backlog and the rest is the honest steady state, renewed by ~1,000 new
rows every day.

So the fix is shape, not volume:

- cap day one at the same target as every other day, and bank the rest
- backfill thin days from that bank before reaching for anything weaker
- never send everything held — the reserve is what buys a flat week
- carry the "came close" section **every** day. A section that only appears when
  there is nothing else is a confession; the same section daily is a feature
- pad with honesty, not filler. Five real matches plus an extra day on the plan
  beats twenty irrelevant ones

`sent_jobs` is the only per-user state that matters: it is what stops day four
repeating day one.

## What is deliberately not done yet

| Thing | Why, and what it needs |
|---|---|
| **Payments** | Switched off as requested. `grantPlan()` writes the entitlement row; Stripe's webhook would call exactly that, so nothing downstream changes. |
| **Google sign-in credentials** | The flow is built and tested; it needs an OAuth client id and secret only the account owner can create. See [Google sign-in](#google-sign-in) below. |
| **Real email** | Set `JOBSTASH_RESEND_KEY` and `JOBSTASH_FROM`. **Do not** switch this on before the sending domain has SPF, DKIM and DMARC — email *is* the product here, and a young domain mailing PDF attachments to strangers is exactly what spam filters catch. |
| **Supabase** | The schema uses no SQLite-only types, ISO-8601 text timestamps, 0/1 booleans and Python-generated ids, so the move is a connection change. |
| **LLM resume parsing** | The deterministic parser needs no key, costs nothing per upload and is auditable. Slot it in at `parse_profile()`; everything downstream takes a `Profile` and does not care where it came from. |

## Google sign-in

Built and tested. It stays switched off until credentials exist: `lib/google.ts`
asks whether both are set at render time, and the button on the auth card is
disabled with a reason when they are not. A button that opens Google and comes
back with `invalid_client` is worse than no button.

### Getting the credentials

Only the owner of the Google account can do this, and it is the one part of
this that cannot be scripted.

1. <https://console.cloud.google.com/> → create a project (any name).
2. **APIs & Services → OAuth consent screen**. External. Fill in the app name,
   a support email and a developer email. While it stays in **Testing**, only
   the addresses listed under *Test users* can sign in — add your own. Nothing
   here needs Google's review: the scopes below are the non-sensitive ones.
3. **APIs & Services → Credentials → Create credentials → OAuth client ID**,
   type **Web application**.
4. Under **Authorised redirect URIs** add, *exactly*:

   ```
   http://localhost:3200/api/auth/google/callback
   ```

   Google compares the whole string. A trailing slash, `127.0.0.1` instead of
   `localhost`, or a different port is a different URI and fails with
   `redirect_uri_mismatch`. Add the deployed one alongside it when there is one.
5. Copy the client id and secret into `web/.env.local` (see
   `web/.env.local.example`):

   ```
   JOBSTASH_GOOGLE_CLIENT_ID=....apps.googleusercontent.com
   JOBSTASH_GOOGLE_CLIENT_SECRET=....
   ```

6. Restart `npm run dev`. Next only reads `.env.local` at boot, so a running
   server will keep insisting sign-in is not configured.

Away from the dev server, set `JOBSTASH_GOOGLE_REDIRECT_URI` to the deployed
callback — and register that one too.

### How it behaves

- **New Google address** → account created, granted the default window, sent to
  `/upload`, because a new account with no resume has nothing to show.
- **Known address** → straight to the dashboard, or to `?next=` if one was set.
- **Address that already has a password account** → linked, *only if Google
  reports the address verified*. The password keeps working afterwards.
- **Unverified address matching an existing account** → refused, with a note to
  sign in with the password. Without that check, anyone who could set an
  unverified Google address to someone else's email would walk into their stash.
- **Cancel on Google's screen** → back to the card, quietly, with no error.

Identity is Google's `sub`, never the email: Google lets people change their
address, and matching on one that moved would hand a stash to whoever inherited
it. The `users.google_sub` column carries a UNIQUE index, and SQLite permits any
number of NULLs in one, which is what lets every password-only account leave it
empty.

### Testing it without credentials

`e2e_google.sh` runs the whole flow against `web/test/google_stub.mjs`, a
stand-in speaking the two endpoints the callback touches. This exists because
the branches that matter — creating an account, linking one that exists, and
*refusing* to link an unverified address — otherwise could not be run even once
before shipping.

```bash
# terminal 1 — the site, pointed at the stub instead of Google
cd web
JOBSTASH_GOOGLE_CLIENT_ID=stub-id JOBSTASH_GOOGLE_CLIENT_SECRET=stub-secret JOBSTASH_GOOGLE_STUB_ORIGIN=http://localhost:3210 npm run dev

# terminal 2 — starts and stops the stub itself
bash e2e_google.sh
```

30 checks: the flow, the redirect rules, linking, and the failure paths.

`JOBSTASH_GOOGLE_STUB_ORIGIN` is refused when `NODE_ENV` is `production`: the
sign-in request throws instead of honouring it. A live server that can be told
where to go and ask whether a password is correct is a total authentication
bypass, and an env var is exactly the thing that leaks in from a misapplied
deploy config.

It throws rather than quietly falling back to the real Google, because a stub
that silently did nothing would mean tests passing against Google itself and
proving nothing. The blast radius is deliberately the sign-in route and not the
process: a stray variable breaks Google sign-in loudly and leaves the rest of
the site serving.

## Known limits

- The scrapers are tech-heavy, so non-technical professions have a thinner pool
  even though `ROLE_CATALOGUE` covers 14 fields.
- Years-of-experience parsing has roughly 2% false positives on prose that
  mentions a number of years without requiring it.
- `ingest.py --fast` skips Kalibrr, OnlineJobs.ph and JobStreet. Those three are
  scraped rather than API-fed, so they are the slowest and the most fragile.
