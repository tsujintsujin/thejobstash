# TheJobStash — Cloudflare migration handoff

Written 2026-09-12. Covers the session that moved the stack off local
Next.js + SQLite onto Cloudflare and put the site live on
**https://thejobstash.com**.

Read `HANDOFF.md` first — it explains *why the product is shaped the way it
is*, and none of that changed. This file covers only what moved, what is
proven, and what is left.

---

## 1. State right now

**Live and fully functional.** Every path was exercised against the real site,
not asserted.

```
WORKING                                NOT ENABLED  (a choice, not a fault)
https://thejobstash.com                R2 -> "download a past digest" button
sign-up / sign-in / sessions              the emailed PDF is unaffected
the dashboard                          Google sign-in  (needs credentials)
plan changes                           Resend          (still writes outbox/)
the free trial
resume upload
digest preview
delivery (renders HTML + PDF, mails)
ingest.py  ->  writes into D1
Titan email on the domain
```

Live numbers at the time of writing:

| | |
|---|---|
| Job pool | **2,199** across 13 sources, all with description text |
| Accounts | 31 users, 17 profiles, 32 entitlements, 16 deliveries |
| Scorer | up locally **and** through the tunnel |
| `test_matching.py` | **55 / 55** |
| `test_cloudflare.py` | **37 / 37** |

Measured through the whole chain (Worker → tunnel → `py_server.py` → matcher → D1):

| Step | Result |
|---|---|
| Free trial, real PDF resume | 71 matches / 632 near-misses of 1,760 · **10.6 s** |
| Resume upload | parsed 3 years, mid, 20 skills · **0.8 s** |
| Digest preview | 20 strong + 10 near-miss · **7.9 s** |
| Delivery | `.eml` + PDF + HTML into `outbox/` · **13.4 s** |
| Paywall | 70 withheld server-side; payload carried bar widths only — no title, company, url or score |
| `ingest.py --fast` | 952 fetched, **439 new**, 513 dupes → pool 1,760 → 2,199 |

Those timings are honest, not fast: Cloudflare is calling a home machine in
Cebu which then parses a PDF and scores 2,199 rows. That is the cost of the
free-plan architecture, not a bug. Making it sub-second is the Containers/$5
conversation in §3, not a code change.

**UI is unchanged.** The only `.tsx` edits were `as any` casts on `.json()`
results — a type-level change with no runtime effect. No markup, no CSS, no
layout. Measured `scrollWidth 1905` against a `1920` viewport, no overflow.

---

## 2. What moved

| Was | Now |
|---|---|
| Next.js 15, destined for Vercel | Cloudflare Workers via `@opennextjs/cloudflare` |
| `node:sqlite` against `jobstash.db` | **Cloudflare D1** (`jobstash`, region APAC) |
| `lib/py.ts` → `child_process.spawn()` | `lib/py.ts` → `fetch()` over a Cloudflare Tunnel |
| `outbox/*.html` + `*.pdf` on disk | **R2** via `/api/internal/digest` (not enabled, §6.3) |
| `thejobstash.com` on Z.com nameservers | Cloudflare zone, active, Worker on apex + `www` |
| Python read `jobstash.db` directly | Python reads D1 through the site (`d1.py`) |

```
Cloudflare account   Justin.masiga.94@gmail.com
Account id           50f9cad3b450e00277cc20b64018bee4
Zone id              c3b3af87591bb57003abc9a1c0379880
D1 database id       62bf7121-3b14-4af2-bf67-6ae4dabf1a36
Worker               thejobstash   (apex + www custom domains)
Tunnel               jobstash-scorer / 0deacc98-dbec-4010-8076-4923e2841aa7
Scorer hostname      https://scorer.thejobstash.com
Plan                 Workers Free — chosen deliberately, §3
Secrets / ids        .env.cloudflare  (local only, never commit)
```

---

## 3. Decisions taken this session

Settled with Justin directly. Don't relitigate without asking.

| Decision | Choice | Why |
|---|---|---|
| Where the Python lives | **This PC, behind a Cloudflare Tunnel** | Containers would keep everything on Cloudflare but need the $5/mo Paid plan. Justin chose free. |
| Plan | **Free** | $0. Accepted trade: the four Python features are down when this machine is off. |
| How Python reaches the database | **Through the site's own `/api/internal/d1`** | The obvious route — Cloudflare's D1 REST API — means an account-scoped token on a home PC that can reach *every* database in the account. This reaches exactly one, with the secret that already exists for the tunnel. |
| Rewrite the scorer in TypeScript? | **No** | ~80KB of Python, and the single-implementation rule from `HANDOFF.md` §3. Two copies of the scoring rules drift within a week. |
| Daily delivery cron | **Stays in n8n on this PC** | That is where the Python and headless Chrome are. A Cloudflare cron waking a sleeping machine is worse than the machine deciding for itself. `run_delivery.py` now writes into D1. |
| R2 | **Parked** | Free tier is $0, but enabling it is a subscription agreement and a terms acceptance — Justin's call, not the agent's. |
| Nameservers | **Moved to Cloudflare** | Required for a Worker custom domain. Titan's records were verified present before *and* after. |

### The decision everything else follows from

`d1.py` is a **`sqlite3`-shaped shim**, not a rewrite. It exposes
`conn.execute(sql, params).fetchone()`, rows indexed by column name,
`executemany`, `commit`, `close` — precisely the surface this codebase already
used. D1 *is* SQLite, so the SQL needed no change at all.

The consequence: **`matching.py`, `delivery.py`, `resume_parse.py`,
`summarise.py`, `profiles.py` and `render.py` were not touched.** Zero lines.
There is still exactly one implementation of the scoring rules — the only
version of this migration where they could not quietly drift.

`test_cloudflare.py` asserts the shim against real `sqlite3` side by side,
because if it ever stops matching, the symptom is a *wrong digest*, not an
error.

---

## 4. The architecture

```
CLOUDFLARE                                THIS MACHINE
┌─────────────────────────────┐          ┌──────────────────────────┐
│ Worker (Next.js/OpenNext)   │          │ py_server.py  :3300      │
│   pages, sessions, accounts │          │   parse / trial          │
│                             │          │   preview / deliver      │
│   /api/trial     ───────────┼─fetch───▶│                          │
│   /api/resume    ───────────┼─fetch───▶│  resume_parse, matching, │
│   /api/deliver   ───────────┼─fetch───▶│  summarise, render(PDF)  │
│                             │          │                          │
│   /api/internal/d1  ◀───────┼──────────┤  d1.py  (db.init())      │
│   /api/internal/digest ◀────┼──────────┤  r2.py  (rendered pairs) │
│         │            │      │          │                          │
│      ┌──▼──┐     ┌───▼───┐  │          │  ingest.py  ─▶ D1        │
│      │ D1  │     │  R2   │  │          │  run_delivery.py (n8n)   │
│      └─────┘     └───────┘  │          └──────────────────────────┘
└─────────────────────────────┘                    │
         ▲                                         │
         └──── scorer.thejobstash.com ◀── Cloudflare Tunnel (dials OUT)
```

**The tunnel dials out.** Nothing here listens for an inbound connection and no
port is forwarded. That was the rule in `HANDOFF.md` §3 and it still holds.

**The site owns the data; this machine owns the Python.** Anything that does
not need Python is served entirely by Cloudflare and does not care whether this
machine is on. When it is off, the four Python features say *"the scorer is
offline"* — a designed, readable failure, not a 500.

### Running it

```bash
scorer.cmd                   # starts py_server.py + cloudflared together
fix-dns.cmd                  # only if DNS breaks again (§7)

cd web
npm run dev                  # localhost:3200 — NO D1 binding
npm run preview              # the real Worker runtime under workerd
npm run deploy               # build + push
npm run d1:migrate           # apply web/migrations/ to D1
npm run migration:gen        # regenerate 0001_init.sql from db.py's SCHEMA

python ingest.py --fast      # refill the pool (writes straight into D1)
python test_matching.py      # 55 checks
python test_cloudflare.py    # 37 checks — the shim vs real sqlite3
```

`npm run dev` has no D1 binding, so anything touching the database needs
`npm run preview`.

---

## 5. Verified, not assumed

```
GET  /                              200
GET  /signup, /privacy, /terms      200
GET  /login                         307 -> /signup?mode=signin
GET  /dashboard   (signed out)      307 -> /signup?mode=signin
GET  /upload      (signed out)      307 -> /signup?mode=signin&next=%2Fupload
POST /api/auth/signup               200  {"ok":true,"redirect":"/upload"}
POST /api/auth/login   (correct)    200  {"ok":true,"redirect":"/dashboard"}
POST /api/auth/login   (wrong)      401  "Wrong email or password."
GET  /dashboard   (signed in)       200  renders
POST /api/trial                     200  71 matches, 70 withheld
POST /api/resume                    200  3y mid, 20 skills
POST /api/deliver?preview=1         200  20 strong + 10 near-miss
POST /api/deliver                   200  .eml + PDF + HTML written
POST /api/internal/d1  (no auth)    401
POST /api/internal/d1  (bad token)  401
GET  scorer.thejobstash.com/healthz 200
GET  scorer.../stats   (no auth)    401
```

Test accounts created during verification were removed afterwards (31 users,
as before).

---

## 6. What is left

### 6.1 Justin's own login  ← the only one that affects a real person

Workers cap PBKDF2 at **100,000** iterations; every hash written before the
migration used 120,000. Both sides are now pinned to 100,000 and
`test_cloudflare.py` asserts they stay equal — but **21 accounts still carry
120,000-iteration hashes and cannot sign in.**

All 21 are `@demo.test` / e2e throwaways **except
`justin.masiga.94@gmail.com`**, which is the real one.

```bash
cd web
python scripts/rehash_passwords.py --dry     # see what it would do
python scripts/rehash_passwords.py           # do it
```

It resets the known demo accounts to the documented `demo1234` and **lists
anything it cannot touch** — a hash cannot be converted without the plaintext.
`justin.masiga.94@gmail.com` will be in that list: set it deliberately, or just
sign up again, since there is no password-reset flow.

The agent could not run this; the sandbox blocks anything that rewrites stored
credentials.

### 6.2 Keep the scorer up across reboots

`scorer.cmd` dies with its window. Fine for the testing phase, and consistent
with `HANDOFF.md` §2 — but before a paying customer exists:

```bash
cloudflared service install        # needs elevation
```

plus `py_server.py` as a Scheduled Task at logon. Per Justin's notes a
`/SC ONLOGON` task needs elevation, so both are double-click jobs, not agent
actions.

**The migration trigger has not changed:** the first paying customer. A 7-day
plan whose day-4 email did not send because the PC slept is a refund, not
degraded service.

### 6.3 Optional / when wanted

| Thing | What it needs |
|---|---|
| **R2** — the dashboard's "download a past digest" button | Enable R2 in the dashboard ($0, 10 GB free, but a subscription + terms acceptance). Then un-comment `r2_buckets` in `web/wrangler.jsonc` and redeploy. Both routes already handle the binding being absent — that is why the site runs fine without it. Until then `deliveries.html_path` holds a local path and the button answers 503/410. The emailed PDF is unaffected. |
| **Google sign-in** | Still only missing credentials. Redirect URI is now `https://thejobstash.com/api/auth/google/callback`. Put the id/secret in with `npx wrangler secret put`. |
| **Real email (Resend)** | The domain is on Cloudflare now, so SPF/DKIM/DMARC are easy. Titan's records are already there; Resend needs its own. Cloudflare is flagging that there is **no DMARC record** — add one before mailing strangers. `HANDOFF.md` §9 still applies: not before the domain is warm. |
| **Supabase** | No longer the obvious next step. D1 is Postgres-shaped SQLite and is already doing the job. |
| **`Notes/Workspace.md`** | Still has no TheJobStash entry (flagged in `HANDOFF.md` §12). That vault is hand-maintained, so it was left alone again. |

---

## 7. Traps found this session — read before debugging

- **The router refused all DNS.** `192.168.254.254` answered REFUSED to *every*
  name — verified against npm, github, google, pypi, api.cloudflare.com — while
  `1.1.1.1` resolved all of them. Chrome worked only because it uses DoH. It
  masqueraded as "npm is broken", "cloudflared is broken", "ingest is broken":
  one cause, not three. **Fixed** by `fix-dns.cmd` (adapter now `1.1.1.1` /
  `8.8.8.8`). If it returns, that script is the fix and `fix-dns.cmd revert`
  undoes it.
- **A hostname can resolve from a stale Windows cache.** Mid-session
  `thejobstash.com` resolved from Python while `scorer.thejobstash.com` did not,
  because Chrome had populated the cache over DoH. Do not read one success as
  "DNS works now".
- **Workers cap PBKDF2 at 100,000 iterations.** Above it `crypto.subtle` throws
  `NotSupportedError`. It surfaced as a bare 500 on sign-up with an **empty
  body** — the traceback existed only in `wrangler tail`.
  `db.py:PBKDF2_ROUNDS` and `web/lib/db.ts:ROUNDS` **must stay equal**; a
  mismatch does not look like a bug, it looks like everyone typing the wrong
  password.
- **workerd's types make `.json()` return `unknown`** where Next typed it `any`.
  That is what the casts in the routes and client components are for — type
  level only.
- **D1 rejects oversized statements** with `SQLITE_TOOBIG`. Descriptions run to
  several KB, so `export_for_d1.py` batches by **bytes** (80 KB), not rows. A
  fixed 50-rows-per-INSERT failed outright.
- **`seed.sql` must not live in `web/migrations/`** — wrangler scans that
  directory. It is written to `web/seed.sql` and gitignored; it contains real
  emails, password hashes and session tokens.
- **Cloudflare's bot rules 403 `Python-urllib/3.x`** (error 1010) before the
  request reaches the Worker. `d1.py` and `r2.py` set an honest `User-Agent`
  for this. Do not remove it.
- **`cloudflared --dns-resolver-addrs` does not cover edge SRV discovery.** It
  still used the OS resolver, so the flag was not a workaround for the broken
  DNS.
- **npm 11 blocks postinstall scripts.** `esbuild` and `workerd` need theirs to
  fetch platform binaries — `npm approve-scripts`.
- **The first `wrangler deploy` 500'd** on `assets-upload-session`. Transient;
  the retry worked. Not a missing `workers.dev` subdomain.
- **`next dev` has no D1 binding.** Use `npm run preview`.
- Every trap in the original `HANDOFF.md` §8 still applies.

---

## 8. Files

### Added

```
d1.py                                  sqlite3-shaped connection over D1
r2.py                                  uploads a rendered digest via the site
py_server.py                           api_bridge's commands over HTTP
test_cloudflare.py                     37 checks: the shim vs real sqlite3
scorer.cmd                             starts py_server + cloudflared
fix-dns.cmd                            self-elevating DNS repair (§7)
.env.cloudflare                        secrets + ids. LOCAL ONLY
HANDOFF-CLOUDFLARE.md                  this file

web/wrangler.jsonc                     bindings, routes, vars
web/open-next.config.ts                the adapter
web/lib/cf.ts                          the one place bindings are reached for
web/cloudflare-env.d.ts                generated by `npm run cf-typegen`
web/migrations/0001_init.sql           generated from db.py's SCHEMA
web/app/api/internal/d1/route.ts       D1 for the scorer machine
web/app/api/internal/digest/route.ts   R2 upload for rendered digests
web/scripts/gen_migration.py           regenerates the migration from db.py
web/scripts/export_for_d1.py           jobstash.db -> seed.sql
web/scripts/rehash_passwords.py        the 100,000-iteration migration (§6.1)
```

### Changed

```
db.py              init() opens D1 when configured; PBKDF2_ROUNDS = 100_000
api_bridge.py      out() unwinds to run() instead of print + SystemExit, so
                   py_server can call the same commands in-process.
                   The CLI is byte-identical.
run_delivery.py    uploads the rendered pair to R2 and stores the key
README.md          new architecture, running the scorer, deploy commands

web/lib/db.ts      node:sqlite -> D1, async throughout, Web Crypto PBKDF2
web/lib/session.ts node:crypto -> Web Crypto, async D1
web/lib/py.ts      spawn() -> fetch()
web/lib/google.ts  process.env -> the Worker's env binding
web/app/api/*      await the now-async db calls; no temp files; R2 download
web/app/page.tsx, dashboard/page.tsx, signup/page.tsx   await + Promise.all
web/app/*.tsx      casts on .json() only — no UI change
```

### Untouched, deliberately

```
matching.py  profiles.py  resume_parse.py  summarise.py  delivery.py
render.py    mailer.py    ingest.py        sources.py    seed_demo.py
```

Justin's personal `JobHunt/` sweep is likewise untouched, and `db.init()` still
opens the local SQLite file whenever the D1 env vars are absent — so every
existing tool and test keeps working unchanged.

---

## 9. Costs

Everything is on free tiers. Nothing is billed.

| | Free allowance | Current use |
|---|---|---|
| Workers | 100,000 requests/day | negligible |
| Workers CPU | **10 ms per request** | not yet hit — watch this |
| D1 | 5 GB, 5M rows read/day | ~7 MB, 2,199 jobs |
| R2 | 10 GB | not enabled |
| Tunnel | free | 1 |
| Zone | free | 1 |
| Domain | — | thejobstash.com, renews 2027-09-10 at Z.com |

The 10 ms CPU ceiling is the one number worth watching. It has not bitten, but
Next.js server rendering plus a PBKDF2 verification is exactly the shape of
work that can reach it. If sign-in or the dashboard starts throwing, check
`npx wrangler tail thejobstash` for CPU-limit errors — the fix is the $5/mo
Paid plan, which raises it to 5 minutes and is a one-click change with no
rework.

Note the free plan is **not** the reason the scorer is slow. That is the round
trip to a home machine, and only Containers (Paid) would change it.
