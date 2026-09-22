# -*- coding: utf-8 -*-
"""
Turn the shared job pool into one user's digest for one run.

A run scores every posting in the pool against the resume and returns the
best of them. Earlier runs change nothing: the same pool and the same resume
give the same digest, and a role that is still listed and still the best fit
stays in it, because it is still the best fit. New postings displace it only
by scoring higher.

  * show every match the scorer stands behind, ranked, in three tiers. The
    96% thrown away is still the product - `stretch`, everything below
    profile.min_score, never reaches the digest - but hiding the 81 that did
    qualify behind a cap of 20 read as "you only match 20 jobs", which is a
    claim about the reader rather than about the filter.
  * always carry a "came close" section, on good runs too. A section that
    only appears when there is nothing else is a confession; the same section
    every time is a feature.
  * pad with honesty, not filler. Five real matches beat twenty irrelevant ones.
"""
import os, sys, json, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db, matching as M
from resume_parse import profile_from_dict

FLOOR = 8            # below this the run counts as thin
NEAR_MAX = 20        # came-close is capped on purpose: there are hundreds, and
                     # the value of the section is the pattern behind them, not
                     # the volume. A long list of roles you cannot have is a
                     # worse product, not a fuller one.
# A guard, not a product number. Every match above min_score is shown; this
# only stops a freak profile from printing a 5 MB PDF nobody asked for. The
# broadest resume measured against the live pool reaches 58 in a tier.
# ponytail: flat per-tier ceiling, revisit if a real profile ever hits it.
PER_TIER_MAX = 150
POOL_DAYS = 60       # postings first seen longer ago than this are not scored


def _rows_for(conn, since=None):
    # Only what the cleanup stands behind. An unverified posting is one its
    # board stopped listing and verify.py has not cleared yet - hidden until
    # it has, because a dead link in a paid digest is the bug this prevents.
    q = ("SELECT id,fp,source,title,company,location,url,salary,seniority,"
         "posted,description,status,first_seen FROM jobs "
         "WHERE status IN ('valid','login_required')")
    args = []
    if since:
        q += " AND first_seen >= ?"
        args.append(since)
    return [dict(r) for r in conn.execute(q, args)]


def _one_per_job(scored):
    """The pool keeps every board's posting of a role; a digest shows it once.

    Of a role's postings, the one that is a match beats one that is not, then
    the higher score, then a link that opens without a login.
    """
    best = {}
    rank = lambda m: (m.is_match, m.score, m.job.get("status") != "login_required")
    for m in scored:
        k = m.job["fp"]
        if k not in best or rank(m) > rank(best[k]):
            best[k] = m
    return list(best.values())


def _days_ago(n):
    return (datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=n)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resume_name(conn, user_id):
    r = conn.execute("SELECT resume_name FROM profiles WHERE user_id=?",
                     (user_id,)).fetchone()
    return (r["resume_name"] if r else "") or ""


def _work_setup(profile):
    """remote | hybrid | onsite - same rule as web/lib/workSetup.ts."""
    if not profile.wants_local_onsite:
        return "remote"
    return "onsite" if profile.remote_only is False else "hybrid"


def build_digest(conn, user_id, per_tier_max=PER_TIER_MAX):
    """Score the pool for one user and lay out their sections. Writes nothing."""
    pdict = db.get_profile(conn, user_id)
    if not pdict:
        return {"error": "no profile - upload a resume first"}
    profile = profile_from_dict(pdict)

    # The pool is local; conn is the account store (D1). Two stores on
    # purpose - see db.jobs_conn().
    rows = _rows_for(db.jobs_conn(), since=_days_ago(POOL_DAYS))
    # Nothing to score is a broken pipeline, not a disappointing run: a fresh
    # install, a sweep that failed on every board, or a run that arrived while
    # the sweep meant to fill the pool was still going. Scoring an empty pool
    # anyway built a 0-match digest, marked the run done and kept the credit.
    # Erroring here fails the run instead, and a failed run refunds.
    if not rows:
        return {"error": "the job pool is empty - nothing to score yet"}
    scored = _one_per_job(M.score_many(rows, profile))
    matches = sorted((m for m in scored if m.is_match), key=lambda m: -m.score)
    near = [m for m in scored if not m.is_match and m.showable]

    # `stretch` is every match below profile.min_score - the one tier the
    # scorer does not stand behind. It is dropped rather than shown, so every
    # job in every section is one the scorer affirmatively endorses. That is
    # the same filter the old cap of 20 was standing in for, applied on the
    # quality it actually meant instead of on a round number.
    chosen_near = sorted(near, key=lambda m: -m.score)[:NEAR_MAX]
    sections = {
        "strong":       [m for m in matches if m.tier == "strong"][:per_tier_max],
        "worth_a_look": [m for m in matches
                         if m.tier == "worth_a_look"][:per_tier_max],
        "near_miss":    chosen_near,
    }

    # Nothing may appear in two sections. This is asserted rather than trusted
    # because the symptom is a digest that reads as incoherent to a paying
    # user, not an error anyone would see in a log.
    _seen = set()
    for _key, _rows in sections.items():
        for _m in _rows:
            assert _m.job["fp"] not in _seen, (
                "job %r in two sections (%s)" % (_m.job["title"], _key))
            _seen.add(_m.job["fp"])

    # The aggregate is the part no job board gives anyone: not "here are jobs"
    # but "here is what is standing between you and them".
    blockers = {}
    for m in near:
        for b in m.blockers:
            blockers.setdefault(b.kind, 0)
            blockers[b.kind] += 1

    picked = sections["strong"] + sections["worth_a_look"]

    summary = {
        # The date label on the digest and its Past digests row, nothing more.
        "day": db.today_iso(),
        "user_id": user_id,
        "pool_size": len(rows),
        "scored": len(scored),
        # Count exactly what the two match sections render, so the
        # dashboard and the digest header cannot disagree. They read
        # "2 matches" and "7 matches" for the same digest because this
        # counted picked while render.py summed the sections.
        "matches": sum(len(sections[k]) for k in
                       ("strong", "worth_a_look")),
        "near_misses": len(chosen_near),
        "thin": len(picked) < FLOOR,
        "blockers": blockers,
        "blocker_copy": _blocker_copy(blockers),
        # The settings this run was scored with, so a row in the stash keeps
        # saying what it was run with after the user changes any of them.
        # `name` and `setup` are here for the dashboard's row title; a row
        # written before them falls back to the profile as it stands now.
        "profile": {"level": profile.level, "years": profile.years_experience,
                    "country": profile.home_country,
                    "skills": len(profile.strong_skills),
                    "name": _resume_name(conn, user_id),
                    "setup": _work_setup(profile)},
    }

    return {"sections": sections, "summary": summary, "profile": profile}


def _blocker_copy(blockers):
    """One line of plain English per blocker kind, phrased about the roles.

    Never about the reader. People read these on bad days, and "you lack X" is
    a different product from "these roles wanted X".
    """
    label = {
        "geography":     "%d were open only to other locations",
        "seniority":     "%d wanted more years than your resume shows",
        "thin_skills":   "%d leaned on tools that are not on your resume",
        "authorisation": "%d required work authorisation you do not hold",
        "onsite":        "%d were onsite only",
        "remote":        "%d were remote",
        "skill_gap":     "%d centred on a technology you have not listed",
        "clearance":     "%d required a government security clearance",
    }
    out = []
    for kind, n in sorted(blockers.items(), key=lambda kv: -kv[1]):
        if kind in label:
            out.append(label[kind] % n)
    return out

