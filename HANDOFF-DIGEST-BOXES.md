# HANDOFF-DIGEST-BOXES.md — the cap, the three boxes, and what is still open

Covers the work of 2026-09-16: replacing the digest's cap of 20 matches with
the quality it was standing in for, and splitting the result into three
sections that are each a box on the Stash row, a page, and a PDF. Read
`CLAUDE.md` first; this is the reasoning behind the rules it now states.

**End state, verified in real Chrome against a real digest:**

- A digest holds every match at or above `profile.min_score` — 81 for the one
  live profile, against 20 before.
- The Stash row shows one box per section, on one line, widths proportional to
  the job counts, trash at the end.
- A box's label opens that section's page; its corner glyph downloads that
  section's PDF. The page carries `DOWNLOAD` in its heading lane.
- A digest rendered before this change keeps the `View` + `PDF` pair it was
  delivered with.

Shipped as PRs #10 (the boxes), #11 (a regression in #10), #12 (the map).

---

## 1. The cap was never a filter

`delivery.py` capped a digest at `TARGET = 20` matches, and its docstring
defended the number: *"Nobody applies to a hundred jobs, and volume is what a
bad job board sells - the 96% thrown away is the product."*

That argument is right about the 96% and wrong about the 20. The scoring
already threw away everything below `profile.min_score`; the cap then threw
away work the scorer had *endorsed*. Measured against the live pool:

| | |
|---|---|
| Pool scored (60-day window) | 12,955 |
| Matches with no blockers | 107 |
| — `strong` (at or above `min_score + strong_margin`, i.e. 24+) | 23 |
| — `worth_a_look` (at or above `min_score`, i.e. 12–23) | 58 |
| — `stretch` (below `min_score`) | 26 |
| Near-misses the user is allowed to see | 480 |

So 81 jobs cleared the scorer's own bar and 61 of them were being discarded by
a round number. Justin's read of the user-facing effect was the deciding one:
*"if we push out 20 10 only, that raises somewhat 'really? i only match with
20?' — it questions the sites capability."* A cap of 20 does not read as a
filter working. It reads as a claim about the reader.

**What replaced it.** The `stretch` tier is dropped — that is the one tier the
scorer does not stand behind, and dropping it is the 96% argument applied to
the quality it actually meant. Everything above it is shown, uncapped.
`PER_TIER_MAX = 150` exists only so a freak profile cannot print a 5 MB PDF;
the broadest resume measured reaches 58.

`NEAR_MAX` went from 10 to 20 and stays capped. There are 480 available and
that number is not a feature: the value of that section is the pattern behind
the blockers ("14 were open only to other locations"), not the volume. A long
list of roles you cannot have is a worse product, not a fuller one.

---

## 2. How the shape was arrived at, and what was rejected

Worth recording, because the first design would have been wrong in a way that
stays invisible until a specific profile hits it.

**Rejected: rank chunks of 20, labelled "1st Top 20", "2nd", "3rd".** This was
the original request. It splits a *ranking* at arbitrary points — job #20 and
job #21 can have identical scores — so any qualitative label on such a chunk
("Top 20", then "worth a look") asserts a quality boundary that does not
exist. Ordinal labels are honest but read as pagination.

**Rejected: fixed parts per tier (Strong 2 parts, Worth a Look 2 parts).**
Justin asked what happens with 50 strong matches, and that question killed the
design: per-tier caps mean 10 strong matches get dropped while 58 lesser ones
still print. The squeeze must fall on the weakest jobs, never the best.

**Built: one budget, spent best-first, then grouped by tier.** `delivery.py`
sorts by score and filters by tier, so a strong match can never be dropped
while a worth-a-look is shown — the invariant falls out of the ordering rather
than being enforced anywhere.

**Built: three boxes, labels from the tier.** `Strong Matches`, `Worth a Look`,
`Came Close`. These are *earned* labels — they come from the score crossing
`min_score` and `strong_margin` — so unlike a chunk label, they are true.

**Built: box width = job count.** `flex: <count> 1 0` with `min-width: 104px`.
Equal widths would imply equal contents when one box holds 23 and the next 58.
It also does what the original gradient idea was reaching for: a run with 50
strong matches has a visibly fatter green box, and nobody has to be told. The
`min-width` floor means a very lopsided run overstates its smallest box; the
`title` tooltip carries the true count.

**Built: two targets per box.** The label opens the section in the browser, the
corner glyph downloads its PDF. Justin's objection was real — *"some people
would not want to go in, click download"* — and the file-row pattern (click the
name to open, click the icon to save) costs neither camp a second click.

The PDF stays because Justin named a reason worth keeping: it can be read
offline. That is a better argument than the one it replaced.

---

## 3. Box count is the signal, and it varies

Nothing pads. A section with no rows produces no box.

| Available | Row reads as | Boxes |
|---|---|---|
| 23 strong / 58 worth a look *(measured)* | green, fat yellow, coral | 3 |
| 50 strong / 30 | green now dominates | 3 |
| 80 strong / 0 | one green slab, no Worth a Look | 2 |
| 0 strong | Strong box disappears | 2 |
| 0 matches at all | Came Close only | 1 |

The last row is a bad day and looks like one. `render.py` already has thin-run
copy for it (*"A quiet run. Rather than pad this out with roles that do not
fit…"*), but the **dashboard row says nothing** — that is the obvious
follow-up, and it was deliberately left alone.

---

## 4. What it costs

Four PDFs now come out of one digest: the whole thing plus one per section.
The whole-digest PDF is unchanged in purpose — it is what `mailer.py` attaches
and what `DigestPanel`'s ready-modal links to.

| | |
|---|---|
| Score 12,955 jobs | **43s** — still the dominant cost of a run |
| Render + 4 PDFs, concurrent | **6.6s** |
| Same, sequential | ~19s |
| Whole / strong / worth a look / came close | 947 KB / 283 KB / 521 KB / 281 KB |

The prints overlap safely because `_print_pdf` already gave each Chrome its own
throwaway `--user-data-dir`. That was written to stop two *runs* fighting over
the default profile; it is what made parallelism free here.

**A note on the original premise.** The request assumed splitting would be a
lighter load from the PC — *"I imagine this as a lighter load when being sent to
the site from our PC since its 20 max per pdf?"* It is the opposite: four prints
and ~2 MB against one print and 380 KB. Splitting is a reading decision and a
good one; it is not a performance one.

---

## 5. Files, and the two things that needed no migration

| File | What changed |
|---|---|
| `delivery.py` | `TARGET`/`NEAR_MIN` gone, `NEAR_MAX = 20`, `PER_TIER_MAX = 150`, `stretch` dropped, dead fallback removed |
| `render.py` | `SECTION_STYLE` loses `stretch` and gains a box label; `digest_html(only=, delivery_id=)`; `write_digest` returns a parts manifest and prints concurrently; `_print_pdf` split out; selfcheck extended |
| `run_delivery.py` | unpacks the manifest into `summary_json` |
| `web/lib/db.ts` | `summary_json` added to the `deliveriesFor` SELECT |
| `web/app/api/download/[id]/route.ts` | `?part=<key>`, whitelisted |
| `web/app/dashboard/page.tsx` | the box row, and the legacy fallback |

**No schema change.** The parts manifest rides in `deliveries.summary_json`, a
column that already existed and was already written. A row without it predates
the boxes and falls back.

**No new route.** Part files are named `<base>-<key>.<ext>` beside the whole
digest, and the existing download route reaches them by rewriting the extension
on the stored path. `py_server._serve_digest` serves by basename and needed
nothing.

**`?part=` is a whitelist, not a sanitiser.** The value becomes part of a
filename on this machine. It is checked against `PARTS` before use; escaping it
would not be good enough.

---

## 6. Two bugs found by reading, not by testing

**The PDF button vanished from every existing digest (PR #11).** The boxes
replaced the row's `View` + `PDF` pair, and the no-parts fallback offered
`View` alone. Every digest already in a stash has no parts — so PR #10 silently
removed the PDF button from all of them, while the file it pointed at was still
on disk and still served correctly. Caught in self-review after merge, not by
any test, and not by the browser pass, which was driven against a *new* digest.
**The lesson: when a component gains a branch, the old branch is a case that
needs exercising, not one that keeps working by default.**

**`CLAUDE.md` pointed at deleted code (PR #12).** The decision table named
`TARGET = 20` and `NEAR_MIN, NEAR_MAX = 5, 10`. That table is the first thing a
session reads; a wrong line in it is worse than no line.

---

## 7. Hurdles worth not repeating

**A worktree is required, and `node_modules` cannot be a junction.** Other
sessions share this checkout, so its branch must not be switched. `git worktree
add` is the answer, but junctioning `node_modules` back to `D:` fails — webpack
resolves through the junction and then cannot express a `D:` path relative to
`C:` (`Can't resolve './D:/AIO Freelance/.../next/dist/client/next.js'`).
`npm ci` in the worktree takes ~40s and works. Three gitignored files must be
copied in, or the worktree looks broken for reasons unrelated to the change:

- `web/cloudflare-env.d.ts` — without it `tsc` cannot find `D1Database`, and
  the cascade surfaces as unrelated *"implicitly has an 'any' type"* errors.
- `web/.dev.vars` — without `JOBSTASH_PY_TOKEN`, every View and PDF answers
  *"The machine that rendered this digest is offline"*, even with the tunnel up.
- `web/.env.local`.

Delete the two secret files when finished. The worktree costs ~719 MB
(`node_modules` 583 MB, `.next` 134 MB), and `git worktree remove` fails on long
paths inside `node_modules` — clear it with a robocopy mirror from an empty
directory first.

**Local runs still cannot finish**, so the dashboard was tested by seeding
`web/.localdb` directly: a user row, a session row, one delivery row with a real
parts manifest, and one without it to exercise the fallback. The digest files
were rendered into the real `outbox/` so the tunnel served them.

**The Chrome extension blocks `document.cookie`**, so a session cannot be
injected. Signing in through the real form is the way, which means setting a
PBKDF2 hash on the local user — `pbkdf2$100000$<salt>$<hex>`, 100,000 rounds,
matching `db.py PBKDF2_ROUNDS`. It is also the better test.

**`save_to_disk` on the extension's screenshot returns no path** in this build.
For an image to hand over: fetch the page with `curl -b jobstash_session=…`,
rewrite `/_next` to absolute, and screenshot the file with headless Chrome. Use
`pwd -W` for the `file:///` URL — a Git Bash `/c/...` path silently produces
`ERR_FILE_NOT_FOUND`.

---

## 8. Verified, and how

Not by asserting. Driven in real Chrome against an 81-match digest:

- Both box buttons served **byte-identical** files to the rendered PDFs
  (283,449 and 521,325 bytes).
- The `DOWNLOAD` control works **inside the digest CSP sandbox**
  (`default-src 'none'` plus `sandbox`). This was the flagged risk: the link is
  a user-activated same-origin navigation and passes
  `allow-top-navigation-by-user-activation`, but a dead button there would have
  looked perfectly fine.
- The restored legacy PDF button pulled 947,241 bytes, matching the
  whole-digest PDF.
- Tooltips carry true counts (`Worth a Look · 58 jobs`).
- Live on thejobstash.com after deploy: both pre-existing rows kept
  `View` + `PDF`.

`test_matching.py` 61/61 · `test_cloudflare.py` 39/39 · `test_concurrency.py`
7/7. `render.py`'s selfcheck gained assertions for part rendering, download
hrefs, blocker-rollup scoping, and box order.

---

## Still open

| | |
|---|---|
| **The boxes have never been seen on production** | They only render on digests produced after this change, and every row on thejobstash.com predates it. Needs one real run (1 credit of 10). What is live and verified is the fallback path. |
| **A boxed row cannot open the whole digest** | Every control on it carries `part=`. The combined HTML and PDF are still rendered, emailed, and linked from the ready-modal — but once that modal is dismissed they are unreachable from the Stash. This is the collision between the original *"the View will see the whole list"* and the later *"clicking on it opens the View"*. Options: leave it; add a fourth control; or make the date clickable. The date is cheapest and adds nothing to the one-line row. |
| **Colours are `JADE` / `SUN` / `CORAL`, not a green ramp** | The request described hard green fading lighter. The palette already in `render.py` was used instead, so a box matches the section header inside the PDF it opens. Changing it is a three-value edit at `render.py:31`, and the PDF headers move with it. |
| **R2 would 404 every box** | `r2.put_digest` uploads only the whole-digest pair. The download route already derives part keys correctly from an `r2:` path, so only the upload half is missing — about ten lines. Deliberately not written: there is no bucket bound, so not one line of it could be tested. Noted at the call site. |
| **A thin run says nothing on the dashboard** | `render.py` has honest copy for a quiet run; the Stash row does not. |
| `PLAN-REBUILD.md:143` | Still refers to *"the arbitrary `NEAR_MAX = 10` cut"*. Left alone — it is a draft for unbuilt work. |
