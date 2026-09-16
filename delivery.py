# -*- coding: utf-8 -*-
"""
Turn the shared job pool into one user's digest for one run.

A run scores every posting in the pool against the resume and returns the
best of them. Earlier runs change nothing: the same pool and the same resume
give the same digest, and a role that is still listed and still the best fit
stays in it, because it is still the best fit. New postings displace it only
by scoring higher.

  * cap matches at TARGET. Nobody applies to a hundred jobs, and volume is
    what a bad job board sells - the 96% thrown away is the product.
  * always carry a "came close" section, on good runs too. A section that
    only appears when there is nothing else is a confession; the same section
    every time is a feature.
  * pad with honesty, not filler. Five real matches beat twenty irrelevant ones.
"""
import os, sys, json, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db, matching as M
from resume_parse import profile_from_dict

TARGET = 20          # matches in a healthy digest
FLOOR = 8            # below this the run counts as thin
NEAR_MIN, NEAR_MAX = 5, 10
POOL_DAYS = 60       # postings first seen longer ago than this are not scored


def _rows_for(conn, since=None):
    q = ("SELECT fp,source,title,company,location,url,salary,seniority,posted,"
         "description,first_seen FROM jobs")
    args = []
    if since:
        q += " WHERE first_seen >= ?"
        args.append(since)
    return [dict(r) for r in conn.execute(q, args)]


def _days_ago(n):
    return (datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=n)).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_digest(conn, user_id, target=TARGET):
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
    scored = M.score_many(rows, profile)
    matches = sorted((m for m in scored if m.is_match), key=lambda m: -m.score)
    near = [m for m in scored if not m.is_match and m.showable]

    picked = matches[:target]
    chosen_near = sorted(near, key=lambda m: -m.score)[:NEAR_MAX]

    # Stretch comes only from matches, never from `near`. `near` is blocked
    # jobs by definition and already has a section; drawing stretch from it
    # once printed the same posting twice, and offered a role hiring only in
    # Abu Dhabi to someone in the Philippines as something to apply for.
    sections = {
        "strong":       [m for m in picked if m.tier == "strong"],
        "worth_a_look": [m for m in picked if m.tier == "worth_a_look"],
        "stretch":      [m for m in picked if m.tier == "stretch"],
        "near_miss":    chosen_near,
    }

    # A picked match is unblocked by definition, so it must appear somewhere.
    # tier is scored independently of blockers, so one can come out "near_miss"
    # on score alone - and then it belonged to no section at all and silently
    # disappeared from the digest.
    placed = {m.job["fp"] for k in ("strong", "worth_a_look", "stretch")
              for m in sections[k]}
    sections["stretch"] += [m for m in picked if m.job["fp"] not in placed]

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

    summary = {
        # The date label on the digest and its Past digests row, nothing more.
        "day": db.today_iso(),
        "user_id": user_id,
        "pool_size": len(rows),
        "scored": len(scored),
        # Count exactly what the three match sections render, so the
        # dashboard and the digest header cannot disagree. They read
        # "2 matches" and "7 matches" for the same digest because this
        # counted picked while render.py summed the sections.
        "matches": sum(len(sections[k]) for k in
                       ("strong", "worth_a_look", "stretch")),
        "near_misses": len(chosen_near),
        "thin": len(picked) < FLOOR,
        "blockers": blockers,
        "blocker_copy": _blocker_copy(blockers),
        "profile": {"level": profile.level, "years": profile.years_experience,
                    "country": profile.home_country,
                    "skills": len(profile.strong_skills)},
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
        "skill_gap":     "%d centred on a technology you have not listed",
        "clearance":     "%d required a government security clearance",
    }
    out = []
    for kind, n in sorted(blockers.items(), key=lambda kv: -kv[1]):
        if kind in label:
            out.append(label[kind] % n)
    return out

