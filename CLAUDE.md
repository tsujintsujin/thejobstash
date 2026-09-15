# CLAUDE.md — TheJobStash

**Read this first, then `HANDOFF.md`.** This file is the map and the rules.
The two handoffs are the reasoning, and you need them before changing anything
structural:

| Doc | Covers |
|---|---|
| `HANDOFF.md` | Why the product is shaped this way. The scoring model, the delivery shape, the free-trial paywall, Google sign-in's security rules, measured data, 12 fixed bugs. **Still current** — the migration changed none of it. |
| `HANDOFF-CLOUDFLARE.md` | Where it runs now. D1, Workers, the tunnel, what is deployed and what is left. |
| `SPEC-CAPABILITY-PARSER.md` | **Draft, not built.** Reworking `resume_parse.py` from keyword-matching to evidence-based understanding, so the product works for any profession rather than developers. Read before touching the parser. |
| `HANDOFF-DEPLOY-EMAIL.md` | 2026-09-14/15: moving deploys behind GitHub, removing every PC → Cloudflare path, the Google popup fix, Brevo email + DNS. Hurdles, fixes, and what to do better. |
| `PLAN-REBUILD.md` | **Draft, not built.** The eight-phase implementation plan for that spec plus the move from time-boxed plans to credits. Each phase has an exit test. **Phases 7–8 were settled and built 2026-09-14:** credits replace plans and the daily digest is gone. |

Anything in `HANDOFF.md` about Supabase, "no tunnel", or the 1,760-job pool is
superseded by `HANDOFF-CLOUDFLARE.md`. Everything else in it still holds.

---

## What this is

A SaaS over the `JobHunt/` pipeline. Upload a resume once; each time the user
runs it (one credit), the boards are swept if the pool is over 30 minutes old,
the pool is scored against the resume, and the handful worth reading comes back
as a digest — plus the near-misses and exactly what blocked each. **There is no
daily email, and nothing runs on a schedule for a user.**

**Live at https://thejobstash.com.** Every account starts with 1 free credit;
packs of 3 / 5 / 12 cost ₱99 / ₱149 / ₱299 through PayMongo (QR Ph). **Test
pricing is on: every pack charges ₱1** (`web/lib/packs.ts` `TEST_PRICE_PHP`).

Verified 2026-09-16: 11,879 jobs / 13 sources · `test_matching.py` 61/61 ·
`test_cloudflare.py` 39/39.

---

## Where it runs

```
CLOUDFLARE                          THIS PC  (behind an outbound tunnel)
Worker (Next.js via OpenNext)       py_server.py :3300
  pages, auth, sessions, credits      resume_parse · matching · summarise
  D1: accounts only                   render.py (headless Chrome -> PDF)
    users sessions profiles           n8n run workflow (webhook, no schedule)
    payments runs deliveries            -> ingest.py, run_delivery.py
    pool_stats (3 numbers)          jobstash.db  <- THE JOB POOL LIVES HERE
  R2  (not enabled)
  PayMongo checkout + webhook
```

**This PC owns the jobs and the Python; the site owns the accounts.**

The pool is **local by design** (`db.jobs_conn()`). Only the scorer ever reads a
job row; the site wants three counts, which `ingest.py` pushes into D1's
`pool_stats` after every sweep. Keeping the pool in D1 meant this machine pulled
several MB back down through the Worker to score one resume — that is what
exhausted the free plan's 10ms CPU budget on 2026-09-12 and took the home page
down. Do not move it back.

Accounts stay in D1 via `db.init()`. Two stores, on purpose.

Two features need this machine up: resume upload, and running a resume (which
also needs n8n; `scorer.cmd` starts py_server, the tunnel and n8n). Everything
else is pure Cloudflare and does not care if it is off; those two then say "the
scorer is offline" by design, and a run that cannot start hands its credit back.

`npm run dev` runs against a local D1 in `web/.localdb` (tables from
`npm run d1:local`, no jobs). It never touches the live database.

---

## The business flow — where each decision lives

Read this before changing product behaviour. Most of it is Python, not TS.

| Decision | Lives in |
|---|---|
| Is this job a match, and what blocked it | `matching.py:404 score()` — the scorer |
| Geography / timezone / visa gating | `matching.py:323 classify_geo()` |
| Which blockers a user is allowed to see | `matching.py:60 SHOWABLE_BLOCKERS` |
| How many jobs a digest holds | `delivery.py:31` — `TARGET = 20`, `FLOOR = 8` |
| Near-miss quota | `delivery.py:33` — `NEAR_MIN, NEAR_MAX = 5, 10` |
| How far back postings are scored | `delivery.py POOL_DAYS = 60` |
| Assembling one run's digest | `delivery.py build_digest()` |
| Prices, pack sizes, the ₱1 test price | `web/lib/packs.ts` — the only place prices live |
| The free credit | `users.credits DEFAULT 1`, `web/migrations/0003_credits.sql` (copy reads `FREE_CREDITS`) |
| Taking a credit for a run, race-safe | `web/lib/db.ts startRun()`, called by `/api/deliver` — takes the credit only while that account has no open run, in the same batch, so one account runs once at a time |
| Showing a run in progress | `web/lib/db.ts openRunFor()` → `dashboard/page.tsx` → `DigestPanel`'s bar. Server-side, so a refresh or a fresh sign-in resumes it instead of offering a second run |
| Refunding a failed run, once | `web/lib/db.ts failRun()` · `run_delivery.py fail_run()` · the workflow's **Fail the run** node (`run_delivery.py --fail`) · 45-min stale sweep in `/api/runs/[id]`, the last resort for when this machine is gone entirely |
| Score the pool as it stands; sweep after if 30+ min old (empty pool only: sweep first) | `n8n/build_saas_workflow.py FRESH_MINUTES = 30` · `ingest.py --age` · `ingest.lock` |
| Opening a digest (modal, View, PDF) | `web/app/api/download/[id]/route.ts` — one route, reached from `DigestPanel`'s ready-modal and the Past digests rows |
| Making a QR Ph code / turning a payment into credits | `web/lib/paymongo.ts createQr()` / `settle()` via `/api/pay`, `/api/pay/[id]` (the buy modal polls it), `/api/pay/webhook` |
| Which payment methods are offered | QR Ph only, shown in our own modal (`web/app/dashboard/BuyCredits.tsx`). GCash and cards, once PayMongo approves them, need their own flows |
| Resume file to Profile | `resume_parse.py` |
| A user as data | `profiles.py` |
| Scraping the pool | `ingest.py` -> `JobHunt/sources.py` (13 boards) |
| Schema | `db.py` — `jobs users profiles payments runs deliveries trial_runs sessions`; live D1 changes go in `web/migrations/` |

`api_bridge.py` is the JSON contract between the site and the Python; the
commands are `parse`, `profile`, `preview`, `deliver`, `stats`.
`py_server.py` serves `parse` and `preview` over HTTP, plus `/run`, which hands a run to n8n. Change the shape of one
and both the CLI and the site change together — that is the point.

### Changing prices is a one-file edit

`web/lib/packs.ts` holds every pack, price and the test price; the home page,
the dashboard and checkout all read it. **Before real sales, set
`TEST_PRICE_PHP = null`.** The nine-file plan-id sprawl went with the plans
themselves; do not reintroduce pack ids anywhere else.

---

## Non-negotiables

Break these and the failure is silent or a security hole. All are load-bearing
on a live site.

1. **Nothing in a digest is withheld, and a credit is what buys a run.** The
   free-trial paywall went on 2026-09-13; time-boxed plans and the daily email
   went on 2026-09-14. `/api/deliver` takes one credit before anything runs, and
   a run that fails or never starts gives it back. Credits are added **only**
   by `settle()`, which re-reads the checkout from PayMongo's API, never from
   the browser or the webhook body. `HANDOFF.md` §4's daily shape and §7's
   paywall are superseded.
2. **`db.py:207 PBKDF2_ROUNDS` and `web/lib/db.ts:39 ROUNDS` must stay equal**,
   and workerd caps at 100,000. A mismatch does not look like a bug — it looks
   like every user typing the wrong password. `test_cloudflare.py` asserts it.
3. **One implementation of the scoring rules.** `d1.py` is a `sqlite3`-shaped
   shim precisely so `matching.py`, `delivery.py`, `render.py`,
   `resume_parse.py`, `summarise.py` and `profiles.py` never needed a second
   copy. Do not port scoring to TypeScript. (`HANDOFF-CLOUDFLARE.md` §3)
4. **`JobHunt/` is Justin's personal sweep and is never modified.**
   `sources.py` is imported read-only. Its workflow id `jobhuntdaily0001` must
   never be reused — n8n keys imports on the id and would overwrite it.
5. **The tunnel dials out.** Nothing here listens; no port is forwarded.
6. **Google sign-in:** identity is Google's `sub`, never the email; link to an
   existing account only on a *verified* address; `state` is checked on return.
   (`HANDOFF.md` §13 — read it before touching that route.)
7. **Never commit** `.env.cloudflare`, `jobstash.db`, `web/seed.sql`, `outbox/`
   — real accounts, password hashes, session tokens, subscriber emails.

---

## Two things live outside this repo

```
D:\AIO Freelance\JobHunt\sources.py   10 of the 13 scrapers — imported read-only.
                                      kalibrr, onlinejobs, jobstreet come from
                                      stash_sources.py instead: JobHunt's copies
                                      search developer keywords, these scrape
                                      every profession. Override dir: JOBHUNT_DIR
D:\AIO Freelance\n8n\                 build_saas_workflow.py +
                                      workflows/jobhunt-saas.json
                                      the run workflow: webhook, no schedule.
                                      ingest.py --age / --json, run_delivery.py
                                      --json --user <id> --run <run_id>
                                      No node may end the run early: each one
                                      continues on error so every failure
                                      reaches the Fail the run node, which is
                                      run_delivery.py --fail --run <run_id> -
                                      it closes the run and returns the credit
                                      in seconds instead of after 45 minutes.
                                      active:true in the JSON on purpose: an
                                      import applies it, and false silently
                                      switched the webhook off.
                                      Pruning (jobs unlisted 30+ days) is part
                                      of every sweep in ingest.py - there is no
                                      separate prune job or schedule.
```

Neither is under version control. **The workflow that actually runs a resume
is not in this repo** — if you change `run_delivery.py`'s interface, the
workflow JSON changes too, and nothing will remind you.

Import with `N8N_USER_FOLDER` pointing at the n8n folder, as `start_n8n.cmd`
sets it. Without it, `n8n import:workflow` writes into `~/.n8n`, reports
success, and the running n8n never sees the workflow. Stop n8n, import, then
`n8n publish:workflow --id=jobhuntsaas0001`.

---

## Running it

```bash
scorer.cmd                   # py_server.py + cloudflared + n8n
fix-dns.cmd                  # only if DNS breaks (HANDOFF-CLOUDFLARE.md §7)
```

```bash
npm run dev                  # cd web — localhost:3200, local D1 in .localdb
npm run d1:local             # create the local D1's tables
npm run deploy               # refuses on purpose — see below
```

No command on this PC changes anything on Cloudflare. `preview`, `d1:migrate`
and `d1:seed` were removed 2026-09-15; the PC's wrangler is logged out.

```bash
python ingest.py --fast      # refill the pool -> D1
python test_matching.py      # 61 checks
python test_cloudflare.py    # 39 checks — the D1 shim vs real sqlite3
```

**Deploys go PC → GitHub → Cloudflare, never PC → Cloudflare.** Push to
`master` on `tsujintsujin/thejobstash`; Cloudflare Workers Builds (connected to
the repo, root `web/`) runs `npx opennextjs-cloudflare build` then
`npx opennextjs-cloudflare deploy`. Connected 2026-09-14: GitHub app
"Cloudflare Workers and Pages" is installed on `tsujintsujin` for this one repo
only; preview builds are off; Cloudflare holds its own build token ("Workers
Builds - 2026-09-14 20:45"). `npm run deploy` exits 1 so nobody ships
code that is not on GitHub. Emergency undo is the Cloudflare dashboard
(Worker → Deployments → roll back), not a local deploy.

Google sign-in's client id/secret are **Worker secrets** (set 2026-09-14), not
`.env.local` — a build from GitHub has no `.env.local`. A new file in
`web/migrations/` is **not** applied by a deploy: run its SQL in the Cloudflare
dashboard's D1 console for `jobstash`, then check `d1_migrations`.

---

## Open items

| | |
|---|---|
| Justin's *password* login is still broken | 21 accounts carry 120,000-round hashes that workerd cannot verify. **No longer urgent:** as of 2026-09-12 `justin.masiga.94@gmail.com` is linked to Google and signs in that way. The stale hash is still on the row, so the password path stays broken until someone runs `python web/scripts/rehash_passwords.py`. |
| Scorer dies with its window | No scheduled task, no `cloudflared` or n8n service. Both need elevation. Must be fixed **before the first paying customer**: while it is down nobody can spend credits they paid for. Failed starts are refunded, but that is not a product. |
| R2 not enabled | `r2_buckets` is commented out at `web/wrangler.jsonc:49`. Only affects the dashboard's "download a past digest" button; the emailed PDF is unaffected. Needs a terms acceptance — Justin's call. |
| ~~Google sign-in~~ **working** | Live and verified end to end 2026-09-12 (linked, not duplicated). The credentials reach production by Next **inlining `.env.local` at build time**, not as Cloudflare secrets — so `wrangler secret list` shows nothing and rotating them needs a rebuild. Worth moving to `wrangler secret put` eventually. `JOBSTASH_GOOGLE_REDIRECT_URI` is now a var in `wrangler.jsonc`; without it `googleRedirectUri()` silently falls back to `http://localhost:3200/...` and every production sign-in dies on `redirect_uri_mismatch`. |
| Email | **Sign-up codes: live via Brevo** since 2026-09-15 (`web/lib/mail.ts`, Worker secret `JOBSTASH_BREVO_KEY`, sender `noreply@thejobstash.com`, domain authenticated, DMARC `p=none`). Digest mail (`mailer.py`) still references Resend and writes `.eml` to `outbox/`. See `HANDOFF-DEPLOY-EMAIL.md`. |
| Payments | PayMongo, account TSUJIN IT SOLUTIONS. **QR Ph only**: GCash and cards read "Available after your upgrade" pending PayMongo's business-type review; they will need their own flows when approved. `TEST_PRICE_PHP = 1`. Live since 2026-09-14 (Worker version e0d876a4): `PAYMONGO_SECRET_KEY` is a Worker secret, and PayMongo webhook `hook_Hgs5ouGaoTEqCtMwyUhUQMfw` posts `payment.paid` to `https://thejobstash.com/api/pay/webhook`. |

---

## Traps

- **Workers Free gives each request 10ms of CPU, and a cold start pays the
  Next.js module-init cost out of that same budget.** On 2026-09-12 the home
  page 500'd for everyone because `poolStats()` ran three aggregates over
  2,199 job rows on every render. Symptoms were misleading: Cloudflare error
  1102, a React "Element type is invalid" that is a *symptom* of CPU
  starvation rather than a bug, and static pages failing while dynamic ones
  succeeded (warm vs cold isolates). Low traffic means isolates are almost
  always cold, so it does not heal on its own. **Never make a page do work
  proportional to the pool size.**
- **The local D1 has no jobs** — its `pool_stats` row is zeros, so the local
  home page shows 0 postings. That is the local copy, not a bug. Do not debug
  production symptoms against it.
- **Don't run `next build` while the dev server is live** — both write `.next`
  and every route 500s.
- **Port 3200 sticks.** Find it with `netstat -ano`, then
  `taskkill //PID <n> //F`.
- **D1 rejects oversized statements.** `export_for_d1.py` batches by *bytes*
  (80 KB), not rows.
- **Cloudflare 403s `Python-urllib`** (error 1010) before the Worker sees it —
  `d1.py` and `r2.py` set an honest User-Agent. Don't remove it.
- **`seed.sql` must not live in `web/migrations/`** — wrangler scans that dir.
- **Headless Chrome lies about mobile widths.** Measure `scrollWidth` in a real
  browser before "fixing" overflow.
- **A stray Next 14 project at `D:\AIO Freelance\package.json`** shadows module
  resolution; `outputFileTracingRoot` pins around it.
- Full lists: `HANDOFF.md` §8 and `HANDOFF-CLOUDFLARE.md` §7.
