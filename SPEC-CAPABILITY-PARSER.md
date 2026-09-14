# Spec — evidence-based resume understanding

Draft, 2026-09-12. Written for review, not yet built.

Read `CLAUDE.md` first for where things live, and `HANDOFF.md` §3–§5 for why
the scorer is shaped the way it is. This spec changes **one file's job**
(`resume_parse.py`) and adds fields to `profiles.py`. It does not change
`matching.py`, `delivery.py`, `render.py` or the n8n workflow.

---

## 1. The problem

The parser asks *"does this resume contain words from my list?"* — a closed
vocabulary of 231 tokens built out of `ROLE_CATALOGUE`. It should ask
*"what does this resume show this person can do?"*

Measured on the two fixtures in `Resumes/testing samples/`:

| | Justin (dev) | Jecery (teacher → data entry) |
|---|---|---|
| chars read | 7,703 | 2,109 |
| family score | software **37** | admin **5** |
| skills found | **28** | **2** of 8 listed |
| years | 3 | **None** (resume says 11) |
| level | mid | **junior** |
| work setup | remote_only=True | remote_only=True |

Jecery's resume is not thin — it is dense with evidence. It contains almost
none of the *words* the vocabulary knows. Three separate failures:

1. `\bapplication\b` matched *"consistent application of guidelines"* and put
   her on a software profile. **Fixed 2026-09-12.**
2. 2 of 8 skills recognised — "Google Sheets", "Google Forms",
   "recordkeeping" are not in `SKILL_VOCAB`.
3. 11 years read as `None` → junior, because `find_years()` reads only date
   ranges and her resume writes `(10 years)`.

And `remote_only` is **hardcoded `True`** (`resume_parse.py:463`) for every
user ever created — a preference no resume ever stated, silently filtering
every result.

---

## 2. The principle

> If the resume says it, use it. If it does not, do not filter on it.

Every checker returns one of **three** states:

| State | Meaning | Effect on matching |
|---|---|---|
| `PRESENT` | the resume states or evidences it | used as a filter |
| `ABSENT` | the resume is silent | **no filter, in either direction** |
| `CONFLICT` | two parts of the resume disagree | record both, prefer the safer reading, never silently pick |

Binary-plus-a-default is how `remote_only=True` got baked in. The tri-state is
what makes "optional" actually hold. **A new field must never default to a
value that filters.** `None` means unknown, and unknown means match everything.

---

## 3. Where it slots in

```
extract_text()                          unchanged
  ↓
run_checkers(text, sections)            NEW - the whole of this spec
  ↓
Profile(...)                            same dataclass, new optional fields
  ↓
matching.score()                        UNCHANGED
delivery.build_digest()                 UNCHANGED
render / mailer / n8n                   UNCHANGED
```

This is the slot `HANDOFF.md` §9 reserved for the LLM upgrade. Everything
downstream takes a `Profile` and does not care where it came from, so the
single-implementation rule (`HANDOFF-CLOUDFLARE.md` §3) holds.

### The constraint that governs the whole design

`matching.py:428`:

```python
hits = {s for s in profile.strong_skills if tok(s.lower(), body)}
```

A profile term scores **only if that literal token appears in the job
posting's text.** So tagging someone `organized` achieves nothing — no ad says
it meaningfully. Every capability extracted must come back out as **terms that
appear in real job ads.**

Therefore the taxonomy is **two-sided**: patterns that recognise evidence in a
resume, and separate terms emitted for the posting side.

---

## 4. The capability taxonomy

```python
CAPABILITIES = {
  "high_volume_processing": {
     # resume side - what proves the person has done this
     "evidence": [r"high[- ]volume", r"\b\d{2,}\+?\s*(per|a)\s*day\b",
                  r"evaluated .{0,40}volumes", r"repetitive"],
     # job side - what will actually be found in a posting
     "job_terms": ["high volume", "large volume", "data entry", "throughput"],
     "weight": 4,
  },
  "records_management": {
     "evidence": [r"recordkeeping", r"record[- ]keeping",
                  r"maintain(ed|ing)? .{0,30}records", r"documentation"],
     "job_terms": ["records", "recordkeeping", "documentation", "filing"],
     "weight": 4,
  },
  "rubric_adherence": {
     "evidence": [r"\brubrics?\b", r"fixed .{0,20}criteria",
                  r"standardi[sz]ed format", r"established guidelines"],
     "job_terms": ["guidelines", "criteria", "quality standards", "accuracy"],
     "weight": 3,
  },
  # ... one entry per capability
}
```

Output stays `strong_skills: {term: weight}` — the exact shape `Profile`
already carries — so `matching.py` needs no change.

### Weighting

Evidence found in a **work-experience bullet** outranks the same term in a
skills list. A bullet is a claim about work performed; a list item is an
assertion. Current weighting (`find_skills`, base 3, +2 in a skills section,
+1 if it recurs) inverts this. Proposed:

| Source | Weight |
|---|---|
| evidenced in a work bullet | 5 |
| in a skills section **and** evidenced in a bullet | 6 |
| in a skills section only (aspirational) | 3 |
| incidental mention in prose | 2 |

---

## 5. The checkers

### 5.1 Target role — **new, highest priority**

The site's own banner says **"FOR CAREER SWITCHERS."** `find_families()`
derives role families from *past titles*, which for a switcher is backwards.

Jecery states her target twice:
- *"Seeking a remote, non-client-facing role in data entry, data annotation, transcription"*
- *"Open to entry-level roles in data entry, data annotation, transcription"*

Neither is read.

| State | Rule |
|---|---|
| PRESENT | stated target drives role families |
| ABSENT | fall back to history (today's behaviour) |
| CONFLICT | target wins for **targeting**; history still supplies **capability evidence** |

Evidence: `seeking`, `open to`, `looking for`, `target role`, `objective`,
`interested in` + the noun phrase following, and the headline under the name.

### 5.2 Work setup — **new, fixes a live bug**

| Resume says | `work_setup` |
|---|---|
| "available for remote", "work-from-home" | `remote` |
| "open to relocation", "willing to relocate" | `flexible` |
| "hybrid" | `hybrid` |
| "onsite", "on-site only" | `onsite` |
| **nothing** | `None` → **no geography preference filter** |

Replaces the hardcoded `remote_only=True`. Note both fixtures state their
preference in plain English and neither is currently read.

**Migration:** the 17 existing profile rows carry `remote_only`. Treat a
missing `work_setup` as `None`, not as the old default, or every existing user
keeps the silent filter.

### 5.3 Experience duration

> **DECIDED 2026-09-12 (Justin): do NOT build the fallback tiers below.**
> A resume should state **month and year of employment**, not a number of
> years. The parser stays strict — date ranges only — and a resume without
> them gets **told**, as a Resume Health item (§6): *"your roles have no
> dates; add month and year for each."*
>
> This is better than guessing: it keeps HANDOFF §10's precision (no prose
> false positives), and it turns the gap into the product rather than a silent
> wrong answer. The one thing that must still change is §5.3a — an unreadable
> date must stay **unknown**, never collapse to `0`.
>
> The tier design is kept below only as a record of what was considered and
> why it was rejected.

Date ranges are a Western/tech-template convention. Plenty of real resumes
state durations instead, so building around ranges quietly encoded an
assumption about who was applying.

**Four tiers, highest available wins:**

| Tier | Pattern | Confidence | Gives |
|---|---|---|---|
| 1 | `Jun 2023 – Sep 2026` | highest | spans → overlap merge + relevant/total split |
| 2 | `(10 years)` adjacent to a role entry | high | per-role durations → still splits relevant/total |
| 3 | `11 years of experience` in a summary | medium | one global number, no per-role breakdown |
| 4 | nothing | — | `None` → **unknown, no gate either way** |

**Corroboration:** when two tiers agree independently, mark high confidence.
Measured on the Jecery fixture — tier 2 sums to 11, tier 3 claims 11, agreeing
without reference to each other. When they disagree, record `CONFLICT`, prefer
the lower tier number, keep both.

**Guards** — the original design was right to distrust prose; the fix is to
anchor on *structure*, not to start trusting bare numbers:

- tier 2 requires the parenthetical form **adjacent to a role entry**, so
  "3 years of historical data" cannot match
- tier 3 requires the literal phrase `years of experience|work`, so
  "3 years of data" cannot match
- reject values over ~50, and anything inside an EDUCATION block
- never read a posting's "5+ years required" as a resume claim

This keeps HANDOFF §10's ~2% precision concern satisfied while recovering the
resumes it was silently zeroing.

### 5.3a The bug is not the prose rule — it is the collapse

`find_years()` correctly returns `None` for "cannot determine". Then:

```python
years_experience = overrides.get("years_experience", years or 0)
```

`years or 0` turns unknown into **zero**, and `find_level(text, 0)` turns zero
into **junior**. An 11-year professional is then blocked by "Asks for 5+
years" — on a number the parser invented. Fix the collapse as well as the
tiers; either alone is insufficient.

### 5.3b Relevant vs total, for a switcher

Fixing the years does not finish it. The model splits relevant from total, and
`level` comes from **relevant**:

```
total_years     11   (teaching)
relevant_years   0   (to data entry, her stated target)
```

So she moves from "junior, 0 years" to "junior, 0 relevant years" — better,
but still blocked by any experience requirement. Half of that is correct (she
is new to data entry and asks for entry-level); half is wrong, because the
clerical content of those 10 years *is* relevant and her resume evidences it:
recordkeeping, high-volume evaluation, documentation, fixed criteria.

**Therefore: relevance should be judged on transferred capability (§4), not on
whether a past title matches the target family.** Carry both numbers plus the
confidence flag; never collapse to one.

### 5.4 Licence / certification — **the profession-agnostic primitive**

Every filter in the system today is one a developer cares about. Regulated
professions gate on **credential first, skills second**: PRC (nursing,
teaching, engineering), LET, CPA, TESOL, driver's licence restriction codes.

| State | Rule |
|---|---|
| PRESENT | matching credential is a strong positive |
| ABSENT | a job requiring a licence becomes a **near-miss**, never a block |

Absence of a licence on a resume is **not** evidence the person lacks it. The
honest output is a showable blocker — *"requires a PRC licence"* — which is
exactly what the blockers-not-early-returns design exists for. Add
`licence` to `SHOWABLE_BLOCKERS` (`matching.py:60`).

### 5.5 Employment type

Full-time / part-time / contract / freelance / internship. Stated → filter.
Absent → ignore. Extractable from `description` on the job side.

### 5.6 Shift / hours

Graveyard, US hours, EST overlap, fixed weekends. Large in the PH market and a
genuine hard blocker for people who cannot work nights. Partially overlaps the
existing timezone logic — reuse `timezone_window()`, do not duplicate it.

### 5.7 Language

Jecery's resume lists Cebuano (native), Filipino (fluent), English (working,
written). VA, annotation and BPO ads routinely demand English fluency. Stated
→ use. Absent → ignore.

### 5.8 Salary — **soft blocker only**

`salary` resolves on only **14%** of postings (HANDOFF §4). A hard floor would
discard 86% of the pool over missing data rather than bad fit. Show as a
blocker when the posting states a figure; never filter on it.

---

## 6. Test matrix

Each row is a scenario the parser must survive. Fixtures live in
`Resumes/testing samples/`.

### Format
| # | Scenario | Expected |
|---|---|---|
| F1 | dates as `(10 years)` | 11 years, not None |
| F2 | `Jan 2020 – Present` / `2020 to date` / `03/2020` | parsed |
| F3 | two-column PDF | detected as scrambled, not silently garbled |
| F4 | skills in a table (docx ✓, pdf ?) | extracted from both |
| F5 | no section headings at all | degrades, does not zero out |
| F6 | repeated page header/footer | deduped, does not inflate counts |
| F7 | partly Tagalog/Cebuano | not misread as thin |
| F8 | 10-page CV vs 1-page | counts normalised by length |
| F9 | scanned PDF, no text layer | existing thin guard refuses |

### Career shape
| # | Scenario | Expected |
|---|---|---|
| C1 | career switcher (teacher → data entry) | target role wins; history supplies capability |
| C2 | fresh graduate, no employment | no seniority gate; not defaulted to junior |
| C3 | freelancer, 12 short overlapping gigs | not collapsed to 1 year |
| C4 | employment gap | years and level unaffected |
| C5 | returning after 5 years out | no recency penalty |
| C6 | over-qualified (MA applying entry-level) | stated intent overrides level ceiling ← Jecery |
| C7 | portfolio link, no skills list | not read as thin |

### Optionality — every one of these must **not** filter
| # | Resume omits | Expected |
|---|---|---|
| O1 | work setup | matches remote **and** onsite |
| O2 | location entirely | no geo filter |
| O3 | city (country only) | country-level only, no commute logic |
| O4 | years | no seniority gate |
| O5 | salary | never filtered on pay |
| O6 | languages | ignored |
| O7 | licence | licensed roles shown as near-miss |

### Conflict
| # | Scenario | Expected |
|---|---|---|
| X1 | title "Senior", dates total 2 years | trust dates, record conflict |
| X2 | summary claims 11y, ranges sum to 8 | prefer computed, keep claim |
| X3 | skill listed but in no bullet | weight 3, not 5 |

### Regression — must not break
| # | Scenario | Expected |
|---|---|---|
| R1 | Justin's 4 resumes | `software`, 3 years, mid (HANDOFF §5 #3) |
| R2 | `test_matching.py` | 55/55 |
| R3 | `test_cloudflare.py` | 37/37 |

---

## 7. Fixtures needed

Two exist. Four should be written, because the interesting branches cannot be
tested otherwise — the same argument `HANDOFF.md` §13 makes for the Google stub.

```
Resumes/testing samples/
  Justin Masiga - Full CV.pdf         ✓ dev, dense, date ranges
  Jecery_Masiga_Resume_1.docx         ✓ switcher, durations, no tech vocab
  synthetic_fresh_grad.docx           ✗ no employment at all
  synthetic_nurse.docx                ✗ PRC licence, shift work, onsite
  synthetic_freelancer.docx           ✗ 12 overlapping short gigs
  synthetic_no_preferences.docx       ✗ states nothing optional - the O-series
```

---

## 8. Phasing

| Phase | Scope | Why this order |
|---|---|---|
| **1** | work setup (5.2) + duration fallback (5.3) | Small, deterministic, fixes two live bugs, visible on both fixtures immediately |
| **2** | target role (5.1) | Highest product value — the site is sold to career switchers |
| **3** | capability taxonomy (§4) + widened vocabulary | The deep work; needs 1 and 2 to be useful |
| **4** | licence (5.4), employment type (5.5), shift (5.6), language (5.7), salary (5.8) | Breadth; each is independent and additive |

Phase 1 is roughly a day. Phase 3 is the real project.

---

## 9. Open decisions — Justin's call

1. **Re-parse the 17 existing profiles?** Nothing is retroactive: a profile is
   parsed once at upload and frozen. Jecery keeps getting IT jobs until her
   row is re-parsed. Options: re-parse all on deploy, re-parse lazily on next
   delivery, or leave and let users re-upload.
2. **Does stated intent override an inferred seniority ceiling?** Jecery is a
   Master's-holding 11-year professional asking for entry-level work. I say
   yes — intent wins. It needs to be deliberate, because it is the opposite of
   what the scorer does today.
3. **Pool depth.** 15 teaching and 87 clerical jobs of 2,199. Perfect
   extraction cannot match jobs that are not there. This spec pairs with
   ingestion breadth (HANDOFF §11 #3 — Greenhouse/Lever/Ashby/Workable) or
   non-technical users get a better-understood profile and still a thin digest.
4. **LLM or deterministic?** This spec is deterministic: no API key, no
   per-upload cost, auditable, testable. An LLM would extract capability far
   better and slots into the same place. Worth revisiting after Phase 2, when
   there is a test matrix to judge it against.
