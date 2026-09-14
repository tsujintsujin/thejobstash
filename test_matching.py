# -*- coding: utf-8 -*-
"""
Exercises matching.py. Run: python test_matching.py

Reads JobHunt/ (profile.py, jobs.db) but never writes to it.
"""
import dataclasses, os, sys, sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
JOBHUNT = r"D:\AIO Freelance\JobHunt"

from profiles import Profile, from_jobhunt_profile
import matching as M

ok = fail = 0


def check(label, got, want):
    global ok, fail
    if got == want:
        ok += 1
    else:
        fail += 1
        print("  FAIL %-46s got %r  want %r" % (label, got, want))


print("=" * 68)
print("1. parse_years_required")
print("=" * 68)
for text, want in [
    ("we need 5+ years of experience with React",            5),
    ("Minimum 3 years professional experience required",     3),
    ("3-5 years experience in a similar role",               3),
    ("at least 8 yrs hands-on backend work",                 8),
    ("2 to 4 years of commercial experience",                2),
    ("3+ years React, 5+ years overall experience",          3),
    ("0-2 years experience, graduates welcome",              0),
    # negative guards: prose about the company, not a requirement
    ("We have been in business for 15 years",             None),
    ("Founded 12 years ago in Berlin",                    None),
    ("serving customers for over 20 years",               None),
    ("no experience requirement listed at all",           None),
    # a number too large to be a requirement
    ("celebrating 45 years of operating history",         None),
]:
    check(repr(text[:44]), M.parse_years_required(text), want)

print()
print("=" * 68)
print("2. detect_level  (title first, then board field, then years)")
print("=" * 68)
for title, want in [
    ("Senior Staff Engineer",              "principal"),
    ("Senior Engineering Manager",         "lead"),
    ("Lead Frontend Developer",            "lead"),
    ("Lead Generation Specialist",         None),        # not a seniority signal
    ("Senior React Developer",             "senior"),
    ("Junior Web Developer",               "junior"),
    ("Principal Architect",                "principal"),
    ("Head of Engineering",                "exec"),
    ("Frontend Developer",                 None),
]:
    check(title, M.detect_level(title), want)

check("board field 'Mid-level'", M.detect_level("Developer", "Mid-level"), "mid")
check("board junk code '400'",   M.detect_level("Developer", "400"),       None)
check("falls back to years",     M.detect_level("Developer", "", 9),       "lead")

print()
print("=" * 68)
print("2b. timezone windows  (boards state these far more often than countries)")
print("=" * 68)
for loc, want in [
    ("Timezone restricted (UTC-10 to UTC+14)",  (-10, 14)),   # the whole planet
    ("Timezone restricted (UTC-4 to UTC-4)",     (-4, -4)),
    ("Timezone restricted (UTC+1 to UTC+1)",      (1, 1)),
    ("Berlin, Germany",                             None),
    ("",                                            None),
]:
    check("window %r" % loc[:34], M.timezone_window(loc), want)

for loc, want in [
    ("Timezone restricted (UTC-10 to UTC+14)", "timezones UTC-10 to UTC+14"),
    ("Timezone restricted (UTC-4 to UTC-4)",   "the UTC-4 timezone"),
    ("USA, Canada, USA timezones",             "USA, Canada"),
    ("Berlin, Germany",                        "Berlin, Germany"),
    ("",                                       "an unnamed location"),
]:
    check("pretty %r" % loc[:34], M.pretty_location(loc), want)

print()
print("=" * 68)
print("3. the whole scorer, one blocker at a time")
print("=" * 68)

p = Profile(
    user_id="test",
    role_families=[r"\bdevelop(er|ment)\b", r"\bengineer(ing)?\b",
                   r"\bfront.?end\b", r"\bfull.?stack\b"],
    strong_skills={"react": 6, "typescript": 5, "next.js": 5,
                   "javascript": 4, "tailwind": 3},
    min_skill_hits=3, years_experience=3, level="mid",
    home_country="philippines", authorized_in=["ph"],
    sponsorship_targets=["australia", "new zealand"],
    remote_only=True,
)


def job(title, location="", desc="", seniority=""):
    return {"title": title, "company": "Acme", "location": location,
            "description": desc, "seniority": seniority, "url": "http://x"}


cases = [
    ("clean remote match",
     job("Frontend Developer", "Worldwide",
         "remote, worldwide. react typescript next.js tailwind"),
     "match", []),

    ("perfect skills, wrong country",
     job("Frontend Developer", "Berlin, Germany",
         "onsite in Berlin. react typescript next.js tailwind"),
     "near_miss", ["geography"]),

    ("perfect skills, wants 8 years",
     job("Frontend Developer", "Worldwide",
         "remote worldwide. react typescript next.js. "
         "8+ years of professional experience required"),
     "near_miss", ["seniority"]),

    ("right stack, too few overlaps",
     job("Frontend Developer", "Worldwide",
         "remote worldwide, react only, plus graphql and kubernetes"),
     "near_miss", ["thin_skills"]),

    # Changed deliberately 2026-09-12. Nothing on this resume overlaps the
    # posting at all, so it is now "off_field" rather than "thin_skills", and
    # off_field is a veto: the job is hidden instead of printed under "Came
    # close". The old behaviour put roles with zero evidence of fit in front
    # of the reader - an RPA developer role reached a clerical profile on the
    # word "excel", and an HR Coordinator reached it while the digest printed
    # "Centres on work outside your field" beside it. "Came close" has to mean
    # "you almost qualify" or the section is worthless.
    ("role centres on tech never shipped",
     job("Java Developer", "Worldwide",
         "remote worldwide java spring boot microservices"),
     "near_miss", ["off_field", "skill_gap"]),

    ("US-authorisation wall",
     job("Frontend Developer", "Remote (US)",
         "must be a us citizen. react typescript next.js tailwind"),
     "near_miss", ["authorisation"]),

    ("sponsorship offered in a target country",
     job("Frontend Developer", "Auckland, New Zealand",
         "visa sponsorship available, accredited employer. "
         "react typescript next.js tailwind"),
     "match", []),

    ("sponsorship mentioned only to refuse it",
     job("Frontend Developer", "Austin, Texas",
         "visa sponsorship is not available for this role. "
         "react typescript next.js"),
     "near_miss", ["geography"]),

    ("not this person's profession at all",
     job("Registered Nurse", "Manila", "bedside nursing, BLS certified"),
     "excluded", []),

    # UTC-10..+14 spans the planet. Read as a place name this was blocked,
    # which silently threw away real matches on the remote boards.
    ("worldwide timezone window is not a restriction",
     job("Frontend Developer", "Timezone restricted (UTC-10 to UTC+14)",
         "remote. react typescript next.js tailwind"),
     "match", []),

    ("narrow timezone window genuinely is one",
     job("Frontend Developer", "Timezone restricted (UTC-4 to UTC-4)",
         "remote. react typescript next.js tailwind"),
     "near_miss", ["geography"]),
]

for label, j, want_kind, want_blockers in cases:
    m = M.score(j, p)
    if want_kind == "excluded":
        check(label, m, None)
        continue
    if m is None:
        check(label, "excluded", want_kind)
        continue
    got_kind = "match" if m.is_match else "near_miss"
    check(label + " / kind", got_kind, want_kind)
    check(label + " / blockers", m.blocker_kinds, sorted(want_blockers))
    tag = ", ".join(b.detail for b in m.blockers) or m.tier
    print("    %-38s score %3d  %s" % (label[:38], m.score, tag))

# Unknown years must not be read as zero. A resume that never writes a date
# range - most clerical and teaching ones - used to arrive here with
# years_experience 0, which failed every "N+ years" test and gated an 11-year
# professional out of anything asking for experience at all.
p_unknown = dataclasses.replace(p, years_experience=None)
# 4+, not 8+: detect_level reads 8 years as a lead role, which is a separate
# and legitimate gate. This isolates the years test.
m_unknown = M.score(
    job("Frontend Developer", "Worldwide",
        "remote worldwide. react typescript next.js. "
        "4+ years of professional experience required"), p_unknown)
check("unknown years does not gate / blockers", m_unknown.blocker_kinds, [])
check("unknown years does not gate / kind", m_unknown.is_match, True)
print("    %-38s score %3d  %s" % ("unknown years, 4+ wanted",
                                   m_unknown.score, m_unknown.tier))

print()
print("=" * 68)
print("4. real data: 3,730 rows from JobHunt/jobs.db")
print("=" * 68)
print("NOTE: descriptions are not persisted by JobHunt, so this run scores on")
print("title/company/location only. It proves the machinery runs at scale and")
print("that role-family exclusion works; skill and geography numbers will")
print("shift once ingest.py starts storing the body text.")
print()

sys.path.insert(0, JOBHUNT)
import profile as jh_profile                      # read-only
justin = from_jobhunt_profile(jh_profile)

conn = sqlite3.connect(os.path.join(JOBHUNT, "jobs.db"))
rows = [{"title": t, "company": c, "location": l, "url": u,
         "seniority": s, "description": ""}
        for t, c, l, u, s in conn.execute(
            "SELECT title,company,location,url,seniority FROM jobs")]
conn.close()

results = M.score_many(rows, justin)
excluded = len(rows) - len(results)
matches = [m for m in results if m.is_match]
near = [m for m in results if not m.is_match]
showable = [m for m in near if m.showable]

print("  scraped rows          %5d" % len(rows))
print("  excluded (not their profession)  %5d" % excluded)
print("  matches               %5d" % len(matches))
print("  near-misses           %5d  (%d showable)" % (len(near), len(showable)))
print()
print("  match tiers:")
for t in ("strong", "worth_a_look", "stretch"):
    print("    %-14s %4d" % (t, sum(1 for m in matches if m.tier == t)))
print()
print("  why near-misses were blocked:")
counts = {}
for m in near:
    for k in m.blocker_kinds:
        counts[k] = counts.get(k, 0) + 1
for k, n in sorted(counts.items(), key=lambda kv: -kv[1]):
    print("    %-14s %4d" % (k, n))

print()
print("  top 5 showable near-misses, as the digest would phrase them:")
for m in sorted(showable, key=lambda m: -m.score)[:5]:
    print("    [%3d] %-42s %s" % (m.score, m.job["title"][:42],
                                  m.blockers[0].detail))

print()
print("=" * 68)
print("unit checks: %d passed, %d failed" % (ok, fail))
print("=" * 68)
sys.exit(1 if fail else 0)
