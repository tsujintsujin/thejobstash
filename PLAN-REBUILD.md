# Implementation plan — evidence-based matching + credits

Draft, 2026-09-12. Companion to `SPEC-CAPABILITY-PARSER.md`.

Eight phases. Each one ships on its own, changes something visible in the job
list, and has an exit test that must pass before the next begins. Nothing
here breaks the live site mid-flight.

**Open decision blocking Phase 8 only:** does the daily email digest survive
the move to credits, or do credits replace it? Phases 0–7 are correct under
either answer, which is why the question sits at the end instead of the front.

---

## The instrument, before anything else

Every phase is judged by the same question: *does the job list get better?*
That needs something that answers it in one command, offline, without the
site, without sending mail, without consuming anything.

`dry_run` already exists (`delivery.py:52`, `api_bridge.py:106`,
`run_delivery.py --dry`), so this is a wrapper, not new machinery.

---

## Phase 0 — The bench

**No behaviour change.** Build the instrument and freeze current behaviour.

| Deliverable | What it is |
|---|---|
| `bench.py <resume>` | resume file → profile → scored against the **live pool**, dry. Prints: profile summary, N matches, N near-misses, top 20 of each with blockers. |
| `test_resume_parse.py` | Golden assertions of **today's** output for both fixtures, so any later drift is visible. |
| 4 synthetic fixtures | `fresh_grad`, `nurse`, `freelancer`, `no_preferences` (see spec §7) |

**Exit test**
```
python bench.py "Resumes/testing samples/Justin Masiga - Full CV.pdf"
python bench.py "Resumes/testing samples/Jecery_Masiga_Resume_1.docx"
python test_resume_parse.py     # passes against unchanged code
python test_matching.py         # 55/55
```

Baseline to beat, measured today:

| | Justin | Jecery |
|---|---|---|
| families | software (37) | admin (5) |
| skills | 28 | 2 |
| years / level | 3 / mid | **None / junior** |
| work setup | remote_only=True (hardcoded) | remote_only=True (hardcoded) |

---

## Phase 1 — Tri-state checkers + two live bug fixes

Smallest phase with real value. Fixes two bugs that silently affect every
user today.

- Introduce `CheckResult` → `PRESENT` / `ABSENT` / `CONFLICT`
- **Work setup checker** — replaces hardcoded `remote_only=True`
- **Duration fallback** — accept `(10 years)` / "11 years of experience" when
  no date ranges parse
- New `Profile` fields default to `None`, never to a filtering value

**Migration:** 17 existing profile rows carry `remote_only`. A missing
`work_setup` must read as `None`, not as the old default, or every existing
user keeps the silent filter.

**Exit test**
- Jecery: `None/junior` → **11 years / mid+**
- Both fixtures: work setup read from the text, not assumed
- O-series (spec §6): every omitted signal filters nothing
- Justin's 4 resumes: still `software` / 3 / mid
- 55/55, 37/37

---

## Phase 2 — Target role

The site is sold to career switchers; the parser profiles people on past
titles. Jecery states her target twice and neither is read.

- Extract stated intent (`seeking`, `open to`, `looking for`, headline)
- Intent drives role families; history still supplies capability evidence
- `CONFLICT` when they disagree — target wins for targeting

**Exit test**
- Jecery's families: `admin` → data-entry/annotation/transcription targets
- Her bench job list **visibly changes** — this is the first phase where the
  output moves for a real reason
- Justin (no stated target): unchanged, history still drives

---

## Phase 3 — Capability taxonomy

The deep one. Needs 1 and 2 to be worth doing.

- `CAPABILITIES` two-sided table: `evidence` (resume) → `job_terms` (postings)
- Weighting inversion: evidence in a work bullet (5) outranks a skills-list
  assertion (3)
- Widen vocabulary for clerical/admin — Google Sheets, Google Forms,
  recordkeeping, transcription, data annotation

**Exit test**
- Jecery: 2 skills → 8+, each traceable to a line in her resume
- Justin: 28 skills stable (±2), no new false positives
- Bench near-miss count rises for Jecery, not for Justin
- 55/55, 37/37

---

## Phase 4 — Job-side requirement extraction ← **independent, can start early**

**This phase does not depend on Phases 1–3.** It is the job half of the
problem and can be built in parallel. Given the priority on job-list quality,
it is the one to pull forward.

- Extract requirements from `jobs.description` into structured items
- Classify each **hard** (licence, authorisation, years) vs **soft**
  (nice-to-have tools)
- Measure extraction coverage across all 2,199 live rows

**Exit test**
- Report: % of the pool with ≥1 extractable requirement. HANDOFF §4 measured
  **26%** on 880 postings — that is the number to beat.
- Hand-check 20 postings: extracted requirements match what a human reads
- No change to matching yet — extraction only, verified in isolation

---

## Phase 5 — Coverage model and job-list output ← **the crucial one**

Where the job list actually changes shape.

- Three buckets per requirement: `met` / `not_met` / `unknown`
- `coverage = met / (job's requirements)` — denominator is the **job**, so
  having more than asked never dilutes
- Unknowns never counted as failures (they would punish short resumes —
  Jecery 2,109 chars vs Justin 7,703)
- Make `skill_gap` showable with honest copy
- **Rank near-misses by coverage** and drop the arbitrary `NEAR_MAX = 10` cut

Today: 741 near-misses exist, 10 are shown, chosen by score.

**Exit test**
- Bench prints `matches 6 of 9 stated requirements` + what is missing +
  what the resume never mentioned
- Before/after distribution across the live pool for both fixtures
- A posting with no extractable requirements falls back to the blocker list
  and shows **no** percentage — never a fake number
- 55/55, 37/37

---

## Phase 6 — Resume Health

Pure output. The checkers already hold the data.

- Every `ABSENT` → checklist item; every `CONFLICT` → a fix
- **The honesty rule, enforced in code:** only suggest surfacing what the
  resume already evidences.
  - ✅ "Your bullets describe recordkeeping but your skills section omits it."
  - ❌ "Jobs want Python — add Python."
  A suggestion must carry the resume line it came from, or it is not emitted.

**Exit test**
- Jecery's checklist is specific and true, every item traceable to her text
- A fixture with nothing missing produces an empty checklist, not filler
- No item can be generated without a source line (assert this)

---

## Phase 7 — Credits, and unlocking the list

Business-model change. Touches the site, not the scorer.

- Schema: entitlements (time-boxed) → credits (count)
- 1 free credit on signup; 1 credit = 1 scan
- **Remove the paywall** — HANDOFF §7's withholding, randomised bars, trial
  rate limiting all retire
- Centralise the plan/credit constants — currently plan ids are hardcoded in
  **9 places** (`CLAUDE.md` lists them); do not repeat that with credits
- `sent_jobs` must **not** suppress on re-scan: a new profile deserves a fresh
  verdict

**Exit test**
- Signup → 1 credit → scan → full unlocked list + Resume Health
- Second scan without credits refused cleanly
- Re-scan after resume update shows previously-seen jobs again
- 37/37

---

## Phase 8 — The digest decision ⛔ blocked

Needs your answer: do credits **replace** the daily email, or coexist?

If replaced, these retire: `delivery.py`'s `TARGET`/`FLOOR`, banking,
backfill, the never-send-everything reserve, `extend_entitlement`, and half
of `run_delivery.py` — with n8n reduced to ingestion only. That is a lot of
well-reasoned code (HANDOFF §4), so it should be a decision, not a drift.

Ingestion (`ingest.py`, nightly, 13 boards) survives either way.

---

## Sequencing

```
Phase 0  ──┬──────────────────────────────► the bench, always first
           │
           ├─► 1 ─► 2 ─► 3      resume side  (understanding the person)
           │
           └─► 4 ───────────┐   job side     (independent - pull forward)
                            │
                        5 ◄─┘   coverage + job-list output
                            │
                            ├─► 6   Resume Health
                            └─► 7   credits
                                    │
                                    └─► 8  digest decision (blocked)
```

Given the priority on the job list: **0 → 4 → 5** is the shortest path to a
visibly better list, because Phase 4 needs nothing from the resume side.
**0 → 1 → 2** is the shortest path to fixing what is silently broken today.

I would do Phase 0, then run 1 and 4 as the next two, since they cannot
conflict.

---

## Rules for every phase

1. `test_matching.py` 55/55 and `test_cloudflare.py` 37/37 must pass at the
   end of each. Not negotiable — they are the only thing standing between a
   refactor and a wrong digest.
2. Justin's 4 resumes must keep reading `software` / 3 years / mid.
3. No phase changes `matching.py`'s public contract. The `Profile` in,
   scored jobs out shape stays, so `delivery.py` / `render.py` / n8n are
   untouched until Phase 7.
4. Every phase ends with a bench run on both fixtures, pasted into the commit
   message. The diff in the job list *is* the evidence.
