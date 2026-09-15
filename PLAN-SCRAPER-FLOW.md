# PLAN: finish the scraper flow

**Status: instructions only, nothing here is built yet.** Written 2026-09-14,
right after `UPDATE-2026-09-14.md` (keyword-free scraping + 30-day cleanup).
Read that first. It covers what already changed.

---

## 0. The flow this plan finishes

Two loops that never call each other. They only share `jobstash.db` on this PC.

```
LOOP A  keep the pool fresh      this PC · n8n · SWR: every 30 min and/or when a
                                 user's Run finds the pool stale (`ingest.py --age`)
  1. LIST     every board, every page, no keywords          (every run, ~1-2 min)
  2. FULL AD  open a job's page ONLY if it was never opened   (max 300 per run)
  3. SAVE     same company+title -> bump last_seen · new -> insert
  4. COUNTS   push the 3 home-page numbers to D1 (pool_stats)

> **Superseded 2026-09-16:** there is no separate prune job. `ingest.py` prunes jobs unlisted for 30 days as part of every sweep; `prune_jobs.py` and its 06:30 workflow were removed.
LOOP A2 cleanup                  this PC · separate n8n workflow · 06:30 daily
  delete jobs no board has listed for 30 days               (prune_jobs.py, DONE)

LOOP B  a user                   whenever someone uploads
  site -> resume -> tunnel -> py_server.py scores it against jobstash.db (~7s)
       -> matches / near misses / blockers -> site
```

Rules:
- A user is scored against the pool that already exists. A user's Run may
  *start* a sweep when the pool is stale (the SWR chat's design), but the
  user should never have to **wait** for it (§3).
- Scrapes never overlap (`ingest.lock`, already built by the SWR chat).
- Cloudflare only displays; all heavy work stays on this PC.

---

## 1. Where things stand

| Piece | State | Section |
|---|---|---|
| No keywords on Kalibrr / OnlineJobs / JobStreet | ✅ done | n/a |
| OnlineJobs employer = job id (no merging) | ✅ done | n/a |
| 30-day cleanup, own workflow | ✅ built and imported, **not activated** | §4 |
| Home-page counts | ✅ working, checked in Chrome | n/a |
| Mark each job once its full ad is opened | ❌ | §2 |
| Cap full-ad opens at 300 per run | ❌ | §2 |
| No-overlap guard | ✅ built by the SWR chat: `ingest.lock` (stale after 60 min), `ingest.py:40,107,204` | §3 |
| Pool-age check for SWR | ✅ built by the SWR chat: `ingest.py --age` → `{age_minutes, running}` | §3 |
| SWR schedule / trigger in n8n | ⏳ **the other chat's SWR job** | §3 |
| `TheJobStash Daily Run` imported into n8n | ❌ never imported | §4 |
| n8n running, workflows published + active | ❌ needs Justin | §4 |
| Scorer + tunnel survive a closed window / reboot | ❌ needs Justin (UAC) | §5 |

---

## 2. Open each JobStreet ad only once (this repo)

### The problem

`stash_sources.jobstreet()` decides whether to open a job's page with
`ingest.py:129` (the `known` query in `run()`): *"is this URL in the pool with a description over 800 chars?"*
Length is used because nothing records whether the page was ever opened. So:

- **Real ads shorter than 800 chars** (~11%, measured: 15 of 134) are opened
  again **every run, forever**. That's ~700 of today's 6,237 JobStreet jobs, or ~7 min
  per run. At 48 runs/day it's ~34,000 wasted requests a day, which invites a block.
- A job is still **saved** only once (the fingerprint handles that). The waste
  is the page download, not the database.

### The change

**2.1 `db.py`: add a marker column**

- Add `detail_at TEXT` to the `jobs` table in `SCHEMA` (after `description`,
  commented: when the full ad was fetched; NULL = never).
- Add to `MIGRATIONS` (db.py:232) so the existing `jobstash.db` gets it:
  ```python
  ("jobs", "detail_at", "ALTER TABLE jobs ADD COLUMN detail_at TEXT"),
  ```
  `db.jobs_conn()` passes an explicit path, so `init()` takes the local branch
  and runs migrations. **Do not add a D1 migration**: the pool is local only
  (CLAUDE.md "Where it runs").

**2.2 `db.py:305 upsert_job`: record the marker**

- The row may carry `row["detail_fetched"] = True`.
- UPDATE branch: also `detail_at = COALESCE(detail_at, ?)`, passing `now_iso()`
  when fetched and `None` otherwise. Once set, it's never cleared.
- INSERT branch: add `detail_at` to the column list, same value.
- Keep the existing "keep the longer description" rule as is.

**2.3 `stash_sources.py:110 jobstreet()`**

- `DETAIL_CAP = 1500` → **`300`**. Update the `ponytail:` comment: ~3 min
  per run, and the backlog clears in ~16 runs (~8 h at 30-min runs).
- After a page open returns a **non-empty** `full`, set
  `detail_fetched=True` on that row (`_row()` returns a dict, so set the key
  after building it).
- An **empty** result (ad removed, or JobStreet changed its HTML) spends budget
  but does **not** mark the job, so it's retried. If the HTML changed, every run
  burns its 300 on retries and the report in 2.5 shows `details: 0`. That's
  the signal to fix the regex.

**2.4 `ingest.py:129`: change the skip rule**

```python
known = {r["url"] for r in conn.execute(
    "SELECT url FROM jobs WHERE source='jobstreet' AND detail_at IS NOT NULL")}
```

**2.5 `ingest.py run()`: report it**

- Count rows with `detail_fetched` per source, and add `"details": n` to each
  entry in `report`. Adding a key is safe for the n8n parser, which only reads
  `name/count/new/error`.

**2.6 One-off: seed the marker for today's pool**

Run once after the migration:
```sql
UPDATE jobs SET detail_at = first_seen
WHERE source='jobstreet' AND detail_at IS NULL
  AND length(COALESCE(description,'')) > 800;
```
Those 1,562 rows certainly have the full ad. The ~4,675 others get opened once
more over the next runs, then marked. **Back up `jobstash.db` first.**

**2.7 Check (leave one runnable test)**

A small `test_ingest.py` with plain asserts against a temp SQLite file:
- insert with `detail_fetched=True` → `detail_at` set
- upsert the same job again *without* it → `detail_at` unchanged
- `known` query returns that URL and not an unmarked one

Also run `test_matching.py` and `test_cloudflare.py`; both must still pass.

**2.8 Exit test (real run)**

1. `python ingest.py`: note JobStreet's `details` (≤ 300).
2. Run it again right away: `details` must be ≤ 300 and falling across runs
   while the backlog clears.
3. Once `SELECT COUNT(*) FROM jobs WHERE source='jobstreet' AND detail_at IS NULL`
   is near zero, a run's `details` should be roughly the number of JobStreet ads
   **posted since the last run** (tens, not hundreds), and the run should take ~2 min.
4. Open https://thejobstash.com in **real Chrome** and confirm "Live right now"
   matches `SELECT COUNT(*) FROM jobs`. Screenshot it.

---

## 3. For the SWR chat (scheduling): requirements, not code

That work belongs to the other chat. What it needs to know from this side:

> **Superseded 2026-09-16:** there is no separate prune job. `ingest.py` prunes jobs unlisted for 30 days as part of every sweep; `prune_jobs.py` and its 06:30 workflow were removed.
1. **`ingest.py` no longer deletes anything.** Cleanup is `prune_jobs.py` in its
   own workflow. Don't add it back to the scrape.
2. **Overlap: already handled** (`ingest.lock`, a second run exits 0 with
   `{"skipped": "already running"}`). The 60-min stale window is safe: the
   longest sweep measured was 13 min (first run, 1,500 full ads), and §2 cuts
   runs to ~3-5 min. If §2 is **not** built, keep it at 60.
3. **A user's Run must not wait for a sweep.** A sweep takes ~2-5 min after §2,
   and 13 min before it. The site waits up to 180 s for the PC (`web/lib/py.ts:147`),
   but Cloudflare generally cuts a response off at ~100 s (error 524, not tested
   on this setup). So when `--age` says stale: **score the current pool now,
   and start the sweep in the background** (true stale-while-revalidate). Never
   sweep first and then score inside the same request.
   Expected sweep time: ~1-2 min fixed listing cost, plus ~3-5 min while the
   JobStreet backlog clears, then ~2 min. Don't set an n8n timeout below ~15 min.
4. **JobStreet volume**: 48 runs/day × ~73 API calls + a headless browser each
   time. If JobStreet starts returning 403/429 (shows as `jobstreet FAILED` in the
   report), run JobStreet less often (e.g. every 2 h) and keep the JSON boards
   at 30 min.
5. **`push_pool_stats`** then writes D1 48×/day (3 statements each). That's far under
   the free plan's write limit; no action needed.
6. **`JOBSTASH_OPS_WEBHOOK` is not in `n8n/.env`.** The daily-run workflow posts its
   ops report to `$env.JOBSTASH_OPS_WEBHOOK`, so that last node will fail until
   it's added. It's also worth deciding whether an ops post every 30 min is wanted.

---

## 4. n8n: get anything running at all (needs Justin at the desktop)

Current state (checked 2026-09-14 with `n8n list:workflow`): n8n is **not
running**; only `JobHunt Daily Sweep` and `TheJobStash Prune Old Jobs` are
imported. **`TheJobStash Daily Run` (jobhuntsaas0001) was never imported.**

1. Let the SWR chat finish `build_saas_workflow.py`, then regenerate:
   `python build_saas_workflow.py`.
2. With n8n **stopped**, import (a re-import updates by id, never duplicates):
   ```
   set N8N_USER_FOLDER=D:\AIO Freelance\n8n\
   n8n import:workflow --input="D:\AIO Freelance\n8n\workflows\jobhunt-saas.json"
   ```
   The prune workflow is already imported. Re-import it the same way only if
   `build_prune_workflow.py` changes.
3. Start n8n: `n8n\start_n8n.cmd`. `.env` already has `NODES_EXCLUDE`, which
   Execute Command nodes need.
4. In the editor (http://localhost:5678), for **both** TheJobStash workflows:
   **Publish**, then **Activate**. n8n 2.x runs the *published* version only
   (`n8n/WORKFLOW-HANDOFF.md:320`).
5. Check: trigger each once by hand, confirm a green execution, and for the
   daily run confirm the home page count moved (real Chrome, screenshot).

n8n itself also stops when its window closes. Same problem as §5.

---

## 5. Scorer + tunnel always on (needs Justin: UAC)

Loop B needs `py_server.py` and `cloudflared` up. Today `scorer.cmd` dies with its
window, and so does n8n. This must be fixed **before the first paying customer**
(CLAUDE.md Open items).

- **Proper fix:** a Windows scheduled task or service for `scorer.cmd`,
  `cloudflared` and `start_n8n.cmd` that starts at boot. Logon/boot triggers
  and `schtasks /Create /XML` **need elevation**, so Justin has to click Yes on UAC.
  Write the script to self-elevate (`Start-Process -Verb RunAs` on
  `$PSCommandPath`).
- **Stopgap, no admin (not tested here):** shortcuts to the three `.cmd` files in
  `shell:startup`. They start when Justin logs in, but not after a reboot with
  nobody logged in, and a window can still be closed by mistake.
- **Never** `schtasks /Delete` a working task before its replacement is proven
  (global CLAUDE.md).

---

## 6. Order of work

1. §2: marker + cap (this repo, no one else blocked).
2. §3: SWR chat finishes its trigger/schedule (lock and `--age` already exist),
   making sure a user's Run never waits on a sweep.
3. §4: import, publish, activate (Justin).
4. §5: always-on (Justin, UAC).

## Files involved

| File | Section |
|---|---|
| `db.py` (SCHEMA, MIGRATIONS :232, upsert_job :305) | §2 |
| `stash_sources.py` (jobstreet :110) | §2 |
| `ingest.py` (:93 known, run() report) | §2 |
| `test_ingest.py` (new) | §2 |
| `n8n/build_saas_workflow.py`, `n8n/workflows/jobhunt-saas.json` | §3, §4 (SWR chat) |
| `n8n/.env` (`JOBSTASH_OPS_WEBHOOK` missing) | §3 |
| `n8n/workflows/jobstash-prune.json` | §4 (activate only) |
| `scorer.cmd`, `n8n/start_n8n.cmd` | §5 |
