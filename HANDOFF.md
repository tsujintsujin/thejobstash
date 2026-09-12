# TheJobStash — session handoff

Written 2026-09-10. Covers the session that designed and built this project from
nothing, starting from a question about the JobHunt n8n workflow.

Read this before touching anything here. It records the decisions and *why*
they were made, the things measured against real data, and the traps that cost
time. `README.md` covers how to run it; this covers how it got here.

---

## 1. What this is

A SaaS built around the existing `JobHunt/` pipeline. A visitor uploads a
resume; every morning the shared pool of scraped jobs is scored against it and
the handful worth their time is emailed over — plus the ones that came close,
and exactly what blocked each.

**Justin's personal `JobHunt/` sweep is untouched and must stay that way.**

---

## 2. Decisions taken this session

These were settled with Justin directly. Don't relitigate without asking.

| Decision | Choice | Note |
|---|---|---|
| Product shape | Time-boxed prepaid, **not** a subscription | Plans: one_time (1 day), three_day, seven_day |
| Cadence | One email per day, for the plan's length | |
| Deliverable | Dashboard **+** email digest, PDF attached to the email | PDF goes to email, not a download button |
| Dashboard scope | Account only — plan status, resume, past digests | Not a job browser |
| Database | Supabase eventually; SQLite now | Schema already Postgres-shaped |
| Delivery worker | Stays on Justin's PC in n8n **for the testing phase** | His call; migrate at first paying customer |
| Payments | **Off** | `grantPlan()` writes the entitlement; Stripe's webhook would call the same fn |
| Project home | New top-level folder `D:\AIO Freelance\TheJobStash\` | Follows the `Wedd/` precedent |
| Scrapers | Share `JobHunt/sources.py` **read-only** | Boards break constantly; one fix serves both |
| n8n workflow | **New** builder + new workflow, old one untouched | |
| Free trial | Anonymous, no signup, one job visible, rest locked | Added late in the session |

---

## 3. The architecture, and why

### Ingestion is separated from matching

This is the decision everything else follows from.

```
INGESTION (once a day, user-independent)   MATCHING (per user, on demand)
ingest.py → 13 boards → jobs table         resume → profile → SQL + score
minutes, once                              sub-second, any time
```

Justin's original sketch had the scrape happening *inside* the user's request.
That breaks four ways: JobStreet drives Playwright so a sweep is minutes, not
seconds; 100 users means 100 identical hits on RemoteOK and then an IP ban; the
jobs are identical for everyone and only the *scoring* differs; and there were
already 3,730 of them sitting in a file. Scraping once into a shared pool makes
the marginal cost of the five-hundredth subscriber a SQL query.

### The PC connects outward only

Originally the website was going to call into Justin's machine. Inverted: the
PC pushes scraped jobs *up*, the site reads from the database. No tunnel, no
inbound firewall hole, and the site stays up when the PC is off — jobs just get
staler. Residential IP stays as the scraper, which is an asset: datacentre IPs
get blocked far more.

**Caveat that now applies:** once money is involved, the *delivery* path can no
longer live at home. A paid 7-day plan whose day-4 email didn't send because the
PC slept is a refund, not degraded service. Justin chose to keep delivery on the
PC for testing. The migration trigger is the first paying customer, and it stays
cheap **only if n8n remains an orchestrator that shells out to Python** — never
the place logic lives. Hold that line.

### `profile.py` was always the product

`JobHunt/profile.py` is one person hard-coded into a module: weighted skills,
hard gaps, seniority ceiling, geography rules. The SaaS is that file turned into
a row per user. The resume upload just generates the row without making anyone
hand-write it.

### Blockers, not early returns

`JobHunt/jobhunt.py:235` has five early returns that all produce
`0, "reject", [one reason]`. So a perfect React role that happens to be onsite
in Berlin is indistinguishable from a nursing vacancy — both score zero. You
cannot rank near-misses when they're all 0.

`matching.py` computes everything and *collects* blockers. Exactly one check
still excludes outright: role family. A nursing vacancy is not a near-miss for a
developer, and padding a thin day with those is what would genuinely look lazy.

---

## 4. Things measured, not guessed

### Why the reject pile is not what it looks like

From `JobHunt/jobs.db`, 3,589 hard rejects broke down as:

| Reason | Count |
|---|---|
| Title not a role family (not a software job at all) | 2,110 |
| Geography | 647 |
| Too few skill overlaps | 582 |
| Hard gap in title | ~150 |

The 2,110 are nurses, accountants and VAs pulled in by OnlineJobs.ph, Kalibrr
and JobStreet. **For a multi-user product that pile is inventory, not waste** —
it's other people's jobs. The hard-gap list literally names 31 Python, 31
DevOps, 27 Shopify and 24 Java roles.

### The pool does not deplete

Justin worried a 7-day plan would thin out. Measured: `75 → 13 → 8` is **not**
decay heading to zero. Day one was a *backlog* sweep; 8–13 is the honest daily
rate, renewed by ~1,000 genuinely new rows every day, forever.

What looks bad is the **cliff**, not the plateau. So the fix is shape:

- cap day one at the same target as every other day, bank the rest
- backfill thin days from that bank before reaching for anything weaker
- **never send everything held** — the reserve is what buys a flat week
- carry "came close" **every** day. A section that only appears when there's
  nothing else is a confession; the same section daily is a feature
- pad with honesty, not filler — a short day plus a free extra day beats twenty
  irrelevant jobs

Deliberately **not** 100+/day. Nobody applies to a hundred jobs, or reads them.
Volume is what a bad job board sells; the 96% thrown away is the product.

### Description-extraction coverage (880 real postings)

| | Coverage |
|---|---|
| Salary resolved | 14% |
| Responsibilities extracted | 50% |
| Requirements extracted | 26% |
| At least one section | 61% |

Every section in the UI is therefore conditional. Salary is the exception — it
always renders, as "Salary undisclosed" when unknown, because a blank where
money should be looks broken.

---

## 5. Bugs found and fixed (all verified against real data)

1. **Timezone windows read as place names.** `Timezone restricted (UTC-10 to
   UTC+14)` is the entire planet and was classified as blocked, silently
   discarding valid matches. Live matches went 4 → 6 from this fix alone.
2. **Unshippable blocker copy** — literally `"Hiring in Timezone restricted
   (UTC-4 to UTC-4)"`. Now `"Limited to the UTC-4 timezone, and you are on
   UTC+8"`.
3. **Resume parser counted a bootcamp as employment**, and a 160-char lookback
   bled across sections, tagging Justin's actual dev job as *study* and deleting
   the only experience that counted. Context is now the dates' line plus the one
   above. All four of his resumes now read **3 years / mid**, matching
   `profile.py` exactly.
4. **Relevant vs total years** split, so graphic-artist and VA time doesn't
   inflate software seniority.
5. **`better-sqlite3` wouldn't compile** (no C++ toolchain). Switched to Node
   24's built-in `node:sqlite` — zero native deps.
6. **Card text invisible.** The hero sets `color:#fff` and `.card` never set its
   own, so white on white. Fixed on `.card`, `.job`, `.tag`, `.score`, `.stat`,
   `.plan`. **Same bug recurred** for the trial results — fixed properly by
   portalling them out of the hero into `#trial-results`.
7. **`ingest.py` had no `--json` flag** although the workflow calls it that way.
8. `KeyError: 'violet'` in the PDF renderer's CSS interpolation.
9. **Summariser split brand names** — "Adobe Experience **Manager**" broke at
   "Manager" because the verb list matched it. Noun forms now excluded.
10. **Heading regex matched mid-sentence** — "Translate business
    **requirements** into…" started the Requirements section halfway through a
    clause, producing a bullet beginning "Into technical plans". A heading must
    now follow sentence-ending punctuation or carry a colon.

One thing that **looked** like a bug wasn't: mobile appeared to overflow badly
in headless screenshots, but measuring in a real browser gave
`scrollWidth === viewport === 375`. See traps below.

---

## 6. State of things

Verified at handoff: **55/55 unit checks** (`test_matching.py`), **26/26
end-to-end** (`e2e.sh`), **30/30 Google sign-in** (`e2e_google.sh`), pool of
**1,760 jobs across 13 boards**, all with description text.

Seeded accounts (password `demo1234`): `justin@demo.test`,
`richcard@demo.test`.

### Isolation — confirmed clean

`JobHunt/jobhunt.py`, `profile.py`, `sources.py` still dated 09-07/09-09,
predating this session. `n8n/build_workflow.py` and `jobhunt-daily.json` still
09-08.

**The workflow ids differ deliberately.** n8n keys imports on the id, so reusing
`jobhuntdaily0001` would have silently overwritten Justin's working sweep. The
new one is `jobhuntsaas0001` → `n8n/workflows/jobhunt-saas.json`, built by
`n8n/build_saas_workflow.py`.

---

## 7. The free trial, and why the lock is real

`Upload a resume — free` opens a modal instead of a signup form: drop a file →
**Start** enables → scan runs → button flips to **See results**.

Justin's requirement was that the locked jobs be "unrecoverable". A CSS blur is
defeated by anyone who opens DevTools, so **the locked jobs are withheld
server-side**. `api_bridge.py trial` returns one real job plus randomised bar
widths — no title, company, URL or score for anything locked. Audited live:

```
locked subtree textContent : "00|00|00|00|00"   (transparent placeholders)
locked subtree HTML        : <span class="bar" style="width:46%">
links inside locked area   : 0
identifier keys in payload : NONE
```

If you ever change this, keep the paywall in the payload. The blur is
presentation only.

Anonymous scans are rate-limited to 4/hour per IP (`trial_runs` table) and the
uploaded file is deleted in a `finally` block — nothing is stored for a visitor.

---

## 8. Traps that cost time — read before debugging

- **Never run `next build` while the dev server is live.** Both write `.next`;
  the running server then 500s every route. Cost two debugging detours. Dev
  server compile output is enough for verification.
- **Port 3200 sticks.** A dead-looking server keeps the port; `npm run dev`
  reports `EADDRINUSE` and you end up curling a *stale* server. Kill it:
  `netstat -ano | grep ':3200.*LISTENING'` → `taskkill //PID <n> //F`.
- **Headless Chrome screenshots lie about mobile.** Chrome enforces a minimum
  window width, so `--window-size=414,880` renders wider and crops, which looks
  exactly like layout overflow. Measure `document.documentElement.scrollWidth`
  in a real browser before "fixing" anything.
- **The RTK hook eats CLI flags.** `npx next dev -p 3200` failed with
  `unknown option '-p'`. Put the port in the npm script and run `npm run dev`.
- **`form_input` doesn't fire React's `onChange`.** Controlled inputs stay
  empty. Type into the field, or dispatch a real `change` event.
- **Browser-pane click coordinates can mismatch the viewport** (reported an
  800×857 frame against a 892×956 viewport). Driving the page with
  `javascript_tool` is more reliable than clicking.
- **`node:sqlite` returns null-prototype objects.** React Server Components
  refuse to serialise those — `lib/db.ts` copies every row through `plain()` /
  `plainAll()`. Keep doing that for new queries.
- **The Claude-in-Chrome extension never connected this session.** It's
  installed; it needs the Claude side panel open and signed in.
- There is a **stray Next 14 project at the workspace root**
  (`D:\AIO Freelance\package.json`) that shadows module resolution.
  `outputFileTracingRoot` in `next.config.ts` pins around it.

---

## 9. Deliberately not done

| Thing | What it needs |
|---|---|
| Payments | Off by request. `grantPlan()` already writes the entitlement row Stripe's webhook would write — nothing downstream changes. |
| Google sign-in **credentials** | The flow itself is built and tested (see §13). What is missing is only an OAuth client id/secret, which only the account owner can create. |
| Real email | Set `JOBSTASH_RESEND_KEY` + `JOBSTASH_FROM`. **Not before the sending domain has SPF, DKIM and DMARC** — email *is* the product, and a young domain mailing PDF attachments to strangers is exactly what spam filters catch. Currently writes complete `.eml` files to `outbox/`. |
| Supabase | Schema is already Postgres-shaped: no SQLite-only types, ISO-8601 text timestamps, 0/1 booleans, Python-generated ids. A connection change, not a migration. |
| LLM resume parsing | Slot in at `parse_profile()`. Everything downstream takes a `Profile` and doesn't care where it came from. The deterministic parser needs no key, costs nothing per upload and is auditable. |

---

## 10. Known limits

- Scrapers are tech-heavy, so non-technical professions have a thinner pool even
  though `ROLE_CATALOGUE` covers 14 fields.
- Years-of-experience parsing has ~2% false positives on prose mentioning a
  number of years without requiring it.
- `ingest.py --fast` skips Kalibrr, OnlineJobs.ph and JobStreet — the three that
  are scraped rather than API-fed, so the slowest and most fragile. They're also
  the greyest under ToS if this goes commercial.
- Hacker News rows are whole "who is hiring" comments listing many roles, not
  single jobs. `summarise.py` filters the URL-dump artefacts, but the underlying
  data shape is still wrong for a per-job product.
- `sent_jobs` is cleared when a user uploads a **new** resume — deliberate, so a
  career switcher isn't denied every job their old profile had seen.

---

## 11. Suggested next steps

1. **Supabase migration** — schema was written for it; highest leverage.
2. **Stripe behind `/api/plan`** — the route already isolates the decision.
3. **Ingestion breadth** — current caps are one-person-shaped (Himalayas stops
   at 200, The Muse at 3 pages, JobStreet queries the single keyword
   `developer`). Adding ATS aggregators (Greenhouse, Lever, Ashby, Workable)
   is where 1,000/day becomes 10,000/day, and it grows the *addressable market*
   rather than one user's depth.
4. **Signup-side yield estimate** — geography and title gates kill most of the
   pool and both are user attributes. Showing "your filters match ~9 jobs/day,
   widening to these adjacent titles → ~30/day" before payment sets expectations
   and doubles as the anti-refund mechanism.

---

## 12. Not yet done to the vault

`Notes/Workspace.md` has **no entry for TheJobStash**. That index is what stops
a future session scaffolding work in the wrong place, so it should get a line.
Left alone here because that vault is hand-maintained.

---

## 13. Google sign-in (added after the first handoff)

The flow is written, wired into the auth card, and tested. It is switched off
until credentials exist, which is the one part that cannot be done from here:
creating an OAuth client needs a Google Cloud project only the account owner
can make. `README.md` has the console steps.

### Why there is a fake Google in the repo

`web/test/google_stub.mjs` speaks the two endpoints the callback touches, and
`lib/google.ts` will point at it when `JOBSTASH_GOOGLE_STUB_ORIGIN` is set.

Without that seam the branches that actually carry risk - creating an account,
linking one that already exists, and *refusing* to link an unverified address -
could not have been run even once before shipping. "We'll find out in
production" is not a test plan for the code that decides who gets into whose
account.

The override throws when `NODE_ENV` is production rather than being ignored. A
live server that can be told where to go and ask whether a password is correct
is a total authentication bypass, and an env var is exactly what leaks in from
a misapplied deploy config. It throws instead of quietly falling back to the
real Google, because a stub that silently did nothing would mean tests passing
against Google itself and proving nothing. The blast radius is the sign-in
route, not the process: a stray variable breaks Google sign-in loudly and
leaves the rest of the site serving.

### The rules that must not be relaxed

- **Identity is Google's `sub`, never the email.** Google lets people change
  their address; matching on one that moved hands a stash to whoever inherited
  it. Tested: changing the address still reaches the original account.
- **Link to an existing account only when Google says the email is verified.**
  Otherwise anyone who could set an unverified Google address to someone else's
  email walks straight in. Tested, both ways.
- **`state` is checked on the way back.** Without it an attacker can feed
  someone a pre-baked callback URL and land them inside the attacker's account.
  Tested, including that no session comes out of the refusal.
- **The `id_token` signature is not verified**, and that is correct *only*
  because the token arrives from a server-to-server call to Google's token
  endpoint over TLS. If a token ever arrives from a browser instead, it must be
  checked against Google's JWKS first. The stub's junk signature is deliberate:
  it is what makes that assumption visible.

### Bugs found and fixed while testing this

11. **The post-login destination was truncated at a colon.** State and
    destination share one cookie as `state:next`, and `raw.split(":")` dropped
    everything past a second colon - so `/dashboard?tab=a:b` came back as
    `/dashboard?tab=a`. A truncated path is still a valid-looking path, so it
    redirected somewhere real instead of failing visibly. Splits on the first
    colon now.
12. **`createUser()` returned `password_hash: null`** - which is exactly what an
    OAuth-only account looks like. Any caller asking "does this account have a
    password" would have been told no about an account just given one.

### A trap in testing it

Asserting on the *final* URL after following redirects hides refusals. Once a
session exists, `/signup` forwards anyone already signed in to their
destination - so a replayed callback that was correctly rejected still ends on
`/dashboard`, and the test reads as a pass for the wrong reason. Assert on the
callback's own 302 (`%{redirect_url}`), not on where the chain finishes.

### Still open

- No credentials, so the button renders disabled with a reason.
- No way to link Google from the dashboard after the fact; linking only happens
  automatically at callback when the verified address already matches.
- No unlink, and no "set a password" path for a Google-only account. Neither
  matters until someone actually has both.

