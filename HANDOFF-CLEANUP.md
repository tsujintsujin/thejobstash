# HANDOFF — the pool cleanup (2026-09-16)

Why dead postings reached paid digests, what replaced the sweep, and what the
first real round found. Read before touching `ingest.py`, `verify.py`, the
pool's `status` column, or either n8n workflow.

---

## 1. The problem

Justin clicked "Open the posting" on a digest and got:

- **himalayas** — a Gorin Systems role, link landed on `himalayas.app/jobs`.
  Himalayas answers a removed job by redirecting to its index.
- **jobstreet `93908553`** — HTTP 200, page says *"This job is no longer
  advertised"*.

Two causes, both in the old pool:

1. **Nothing ever checked a posting.** A job left the pool only after 30 days
   unlisted, and `POOL_DAYS = 60` kept scoring it the whole time.
2. **One row per company+title.** The same role on four boards was one row
   holding the *first* board's link. When that board dropped it and another
   still listed it, every sweep bumped `last_seen` and the dead link lived on.
   The Gorin row is almost certainly this.

## 2. The shape now

```
n8n "TheJobStash Cleanup" (jobstashclean001)   at n8n start + every 3 hours
  ingest.py --json      scrape -> freshList.db, compare, tag
  verify.py --json      open what was hidden, delete the dead
  ops report

n8n "TheJobStash Run" (jobhuntsaas0001)        per user run
  run_delivery.py       scores status IN (valid, login_required). Never scrapes.
```

| Where a posting stands | Meaning | Scored? |
|---|---|---|
| `valid` | its board lists it, or the verifier found it alive in the last 24 h | yes |
| `login_required` | listed by a board the verifier found behind a login | yes, with a label |
| `unverified` | its board stopped listing it; waiting for the verifier | **no** |
| *(deleted)* | the verifier found it dead; the reason is in `deadRowsDb.db` | — |

Decisions and why (all agreed with Justin in the design chat):

- **Absence is suspicion, a page is proof.** A board that stops listing a job
  only hides it; the verifier decides. Most JobHunt scrapers read a page or two
  (himalayas 200 max, arbeitnow page 1, jobicy 100, onlinejobs ~1-2 days), so
  "not listed" very often means "still open".
- **Every posting is its own row** (`jobs.id` = board + link). The digest
  collapses a role to one card (`delivery._one_per_job`).
- **Short scrape = retry twice, then skip the board.** Otherwise one failed
  board hides every job it has.
- **Title words gone = dead.** Accepted cost: a live job whose employer
  renamed it is dropped (seen once in the first round, onlinejobs 1714481).
- **Timeout / 403 after 3 tries = dead.** But if a board refuses its first 3
  pages, or half its batch, it is flagged **blocked** and none of its refused
  postings are deleted — at that point it is us being blocked, not the jobs
  being gone.
- **Login wall twice in a row = login board.** Its listed jobs show
  "Login Required"; its unlisted ones are deleted.
- **24 h recheck window** (`RECHECK_HOURS`) so a capped board's live jobs are
  re-verified daily, not every 3 hours.
- **800 checks per board per round** (`PER_BOARD_MAX`), 1.5 s apart.

## 3. What each board does to the verifier (probed 2026-09-16)

| Board | Verifier gets in? | A dead posting looks like |
|---|---|---|
| jobstreet | yes | 200 + "This job is no longer advertised", or 404 |
| kalibrr | yes | redirect to `/404` |
| onlinejobs | yes (page shows "Please login … to apply" on live jobs — not a wall) | 410 |
| arbeitnow, jobicy | yes | 410 |
| remoteok, themuse | yes | 404; themuse also "job is no longer available" |
| workingnomads | yes; live links hop to the employer's ATS | redirect to a category page |
| weworkremotely | headless gets **403** on live and dead jobs alike; real Chrome shows dead ones redirect to `/` | flagged blocked from round 2 |
| jobspresso | yes; **live pages say "Position closed? Let us know."** | — |
| hackernews | yes | — |
| **himalayas** | **no** — Cloudflare bot check, plain fetch too | flagged blocked |
| **remotive** | **no** — 403 | flagged blocked |

Blocked boards' unlisted jobs stay hidden and fall to the 30-day prune. They
are never shown, so the Gorin link can no longer reach a digest.

## 4. First round, against a copy of the live pool

(`backups/cleanup-test/`, `JOBSTASH_DB` + `JOBSTASH_SKIP_STATS=1`)

Scrape (13 of 13 boards clean, none retried): 9,776 listed, 525 new,
**5,271 hidden** for checking — mostly the partial boards: onlinejobs 2,344,
arbeitnow 1,283, himalayas 541, jobstreet 598, jobicy 354.

Verify (~55 min, 800 per board): **719 deleted, 1,978 alive**, 2,574 left.

| Board | Checked | Alive | Deleted | Why deleted |
|---|---|---|---|---|
| jobstreet | 598 | 12 | 586 | 328 × 404, 257 × "no longer advertised" |
| onlinejobs | 800 | 767 | 33 | 29 × 410, 4 × title gone (job replaced/renamed) |
| arbeitnow | 800 | 795 | 5 | 410 |
| jobicy | 354 | 329 | 25 | 410 |
| kalibrr | 90 | 62 | 28 | → `/404` |
| remoteok | 23 | 9 | 14 | 404 |
| weworkremotely | 19 | 0 | 19 | 18 × 403, 1 → `/` |
| themuse | 9 | 4 | 5 | 404 / "no longer available" |
| workingnomads | 4 | 0 | 4 | → category page |
| himalayas, remotive | 3 each | — | 0 | **blocked** |

Jobstreet's hidden postings were 98% dead — exactly the case Justin reported.
Left after round 1: onlinejobs 1,544 and arbeitnow 483 (the 800 cap; later
rounds finish them), himalayas 541 and remotive 6 (blocked, hidden).

The live pool was switched to this copy at 21:24 (Manila) on 2026-09-16;
`backups/jobstash-2026-09-16-pre-cleanup.db` is the pool before it.

**Live run afterwards** (justin.masiga.94@gmail.com, thejobstash.com): 75
matches + 20 came close (81 before). Every one of the 95 cards pointed at a
`valid` posting, none in `dead_rows`, no company+title twice, neither of the
two reported links present. Opening all 95 again with the verifier: 88
alive; 5 were 403s from remotive/weworkremotely that are open in real Chrome;
2 were workingnomads hops to an employer form (bug 2 below).

### Bugs the first round and the live check found (fixed, with tests)

1. **"IT Specialist" deleted while live.** Every word of the title was short
   or on the stop list, so the check borrowed the company — onlinejobs'
   placeholder `onlinejobs-<id>`, which is never on the page. `words()` now
   falls back to all of the title's own words. The three deleted postings
   were re-checked and restored in the copy before the switch.
2. **A hop to an employer site was judged on title words.** workingnomads
   sends some postings to Proxify's bare "upload your CV" form. Off-site
   landings are now alive unless a status or closed notice says otherwise.
3. **weworkremotely refuses a headless browser on live postings too.** The
   blocked-board check only looked at the first three pages; wwr's first was
   a redirect, so its 18 refusals were deleted. They were missing from wwr's
   complete category feeds and the two opened by hand were dead, so they were
   most likely right — but for the wrong reason. A board refused on half its
   batch is now flagged blocked and none of its refusals are deleted.

Spot-checked in real Chrome: deleted kalibrr (→ `/404`), workingnomads
(→ category page), weworkremotely ×2 (→ homepage), jobstreet ("no longer
advertised") were all dead; verified-alive arbeitnow, jobicy, jobstreet,
onlinejobs postings were all open. One onlinejobs deletion was a live job with
a rewritten title — the accepted cost above.

## 5. Things that bit

- **This checkout is the live Python.** A test suite opened the live
  `jobstash.db` with the new code and `db._rebuild_jobs` migrated it mid-branch
  (all rows kept, all `valid`). Harmless here, but any change to the pool's
  shape has to be one the running code survives.
- **Every board's header says "Sign in"**, so login detection keys on a login
  URL or a password field with the job's words missing, never on text.
- **Heredocs through the RTK hook** mangled a long Python patch; write patch
  scripts to a file instead.

## 6. Open

- himalayas and remotive can never be verified from here. Their unlisted jobs
  wait out 30 days hidden. A non-headless browser or their APIs might get in.
- The JobHunt scrapers stay partial (JobHunt is read-only). A stash copy of
  arbeitnow/jobicy/himalayas that pages the whole board would cut the
  verifier's load to near zero.
- `jobstashprune001` ("TheJobStash Prune Old Jobs") is still imported in n8n
  from an older design; its script is gone. Deactivate or delete it in the
  n8n UI.
