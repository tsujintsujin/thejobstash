# -*- coding: utf-8 -*-
"""
Golden tests for resume_parse.py. Run: python test_resume_parse.py

Phase 0 of PLAN-REBUILD.md. This file does NOT assert what the parser should
do - it asserts what it does *today*, so that every later phase makes its
change visible instead of silent. Several assertions below are marked BUG:
they lock in behaviour we intend to break, and Phase 1 is expected to flip
them deliberately rather than by accident.

Fixtures live in Resumes/testing samples/ and never move.
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resume_parse as R

SAMPLES = r"D:\AIO Freelance\Resumes\testing samples"

ok = fail = 0
bugs = 0


def check(label, got, want, bug=False):
    global ok, fail, bugs
    if got == want:
        ok += 1
        if bug:
            bugs += 1
            print("  BUG-LOCKED  %-52s %r" % (label, got))
    else:
        fail += 1
        print("  FAIL        %-52s got %r  want %r" % (label, got, want))


def parse(filename):
    text = R.extract_text(os.path.join(SAMPLES, filename))
    assert not text.startswith("__PARSE_ERROR__"), filename
    profile, diag = R.parse_profile(text)
    return profile, diag, text


def case(filename, families, skills, years, total, level, thin=False):
    print("\n%s" % filename)
    p, d, _ = parse(filename)
    check("families", d["families"], families)
    check("skills_found", d["skills_found"], skills)
    check("years", d["years"], years)
    check("total_years", d["total_years"], total)
    check("level", d["level"], level)
    check("country", d["country"], "philippines")
    check("thin", d["thin"], thin)
    return p, d


# ---------------------------------------------------------------------------
# the two real resumes - the pair the whole rebuild is measured against
# ---------------------------------------------------------------------------

p_j, d_j = case("Justin Masiga - Full CV.pdf",
                ["software"], 29, 3, 5, "mid")

# HANDOFF.md section 5 #3: all four of Justin's resumes must read 3 years /
# mid. This is the regression guard for every later phase.
check("justin relevant<total (graphic-artist years excluded)",
      d_j["years"] < d_j["total_years"], True)

# skills went 2 -> 8 on 2026-09-12 when the admin family's vocabulary was
# widened after auditing her excluded pile. Every one traces to a line in her
# resume, so this is the bug-lock below being deliberately broken.
p_c, d_c = case("Jecery_Masiga_Resume_1.docx",
                ["admin"], 8, None, None, "junior")

# BUG: the resume says "11 years of experience" and labels its roles
# "(10 years)" and "(1 year)". find_years() reads only date ranges and finds
# none, so her experience is genuinely unread. The parser staying strict about
# dates is a decision, not a defect (SPEC-CAPABILITY-PARSER.md 5.3).
check("jecery years unread despite 11 stated", d_c["years"], None, bug=True)
# Unknown stays unknown. The `years or 0` collapse that used to sit here made
# her look like a fresh graduate and gated her out of every posting asking for
# experience; score() now skips the seniority test rather than assuming zero.
check("jecery unknown years stay None", p_c.years_experience, None)

# Her "junior" is NOT from that collapse - it comes from _LEVEL_WORDS matching
# "entry-level" in her own sentence. That part is correct and must survive.
check("jecery junior comes from her stated intent", d_c["level"], "junior")

# Fixed 2026-09-12: bare \bapplication\b matched "consistent application of
# guidelines" and put a teacher on a software profile.
check("jecery is not software", "software" in d_c["families"], False)
check("jecery skills now read from her own words", d_c["top_skills"],
      ["data annotation", "data entry", "data organization", "excel",
       "google forms", "google sheets", "recordkeeping", "transcription"])


# ---------------------------------------------------------------------------
# synthetic fixtures - the branches the real pair cannot reach
# ---------------------------------------------------------------------------

# "Administrative Intern" + filing + data encoding now reads as admin as well
# as support, which is what her internship actually describes.
p_f, d_f = case("synthetic_fresh_grad.txt", ["admin", "support"], 6, None,
                None, "junior")
# No employment at all. years=None is right; the danger is a later phase
# inventing a number for her.
check("fresh grad has no employment years", d_f["years"], None)

p_n, d_n = case("synthetic_nurse.txt", ["healthcare"], 4, 6, 6, "senior")
# BUG: no licence checker exists, so a PRC-licensed RN carries no credential
# at all. This is the profession-agnostic gap in SPEC section 5.4.
check("nurse licence not captured anywhere",
      any("prc" in s or "licen" in s for s in d_n["top_skills"]), False, bug=True)
# BUG: tenure read as rank. A staff nurse with 6 years is experienced, not
# "senior" - no title in the resume claims seniority.
check("nurse level inflated from tenure", d_n["level"], "senior", bug=True)

p_b, d_b = case("synthetic_no_preferences.txt", ["finance"], 4, 8, 8, "lead")
# BUG: same ladder, worse. An 8-year bookkeeper is labelled "lead", which
# mismatches every junior and mid posting in matching.py.
check("bookkeeper labelled lead on tenure alone", d_b["level"], "lead", bug=True)

p_r, d_r = case("synthetic_freelancer.txt", ["design"], 7, 1, 1, "junior")
# 12 gigs from Jan 2024 to Sep 2025 merge to ~1 year. Overlap merging is
# working as designed; recorded so a later change to it is visible.
check("freelancer overlapping gigs merged", d_r["years"], 1)


# ---------------------------------------------------------------------------
# optionality - SPEC section 2. Every one of these is currently ASSERTED
# rather than read, which is the thing Phase 1 fixes.
# ---------------------------------------------------------------------------

print("\noptionality (SPEC section 2)")
for name, p in (("justin", p_j), ("jecery", p_c), ("fresh_grad", p_f),
                ("nurse", p_n), ("bookkeeper", p_b), ("freelancer", p_r)):
    # BUG: hardcoded at resume_parse.py:463 for every user ever created.
    # The nurse explicitly says "Open to onsite roles in Davao Region" and
    # still comes out remote-only.
    check("%s remote_only hardcoded True" % name, p.remote_only, True, bug=True)

# The nurse states onsite willingness in plain English and it is not read.
_, _, nurse_text = parse("synthetic_nurse.txt")
check("nurse text does say onsite", "onsite" in nurse_text.lower(), True)

# The bookkeeper states no preference at all - so nothing should be assumed.
_, _, bk_text = parse("synthetic_no_preferences.txt")
check("bookkeeper states no work setup",
      any(w in bk_text.lower() for w in ("remote", "onsite", "hybrid")), False)


print("\n" + "=" * 68)
print("resume parse checks: %d passed, %d failed  (%d lock in known bugs)"
      % (ok, fail, bugs))
print("=" * 68)
sys.exit(1 if fail else 0)
