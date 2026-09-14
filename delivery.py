# -*- coding: utf-8 -*-
"""
Turn the shared job pool into one user's digest for one run.

The shape of the problem, from the numbers in JobHunt's own database: a first
run finds ~75 matches for a narrow profile, then later runs settle at 8-13
new ones. Sent raw, that reads as 75 then 13 - a cliff, and a cliff reads as
"the product broke". The pool is not actually running out; the first run was a
backlog and the rest is the honest steady state.

So the fix is shape, not volume:

  * cap the first run at the same target as every other run and bank the rest
  * backfill thin runs from that bank before reaching for anything weaker
  * never send everything held - the reserve is what keeps a later run worth
    its credit
  * always carry a "came close" section, on good runs too. A section that
    only appears when there is nothing else is a confession; the same section
    every time is a feature.
  * pad with honesty, not filler. Five real matches beat twenty irrelevant ones.

Deliberately NOT 100+ jobs a run. Nobody applies to a hundred jobs, and volume
is what a bad job board sells - the 96% thrown away is the product.
"""
import os, sys, json, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db, matching as M
from resume_parse import profile_from_dict

TARGET = 20          # matches in a healthy digest
FLOOR = 8            # below this the day counts as thin
NEAR_MIN, NEAR_MAX = 5, 10
POOL_DAYS = 60       # how far back a backlog sweep reaches


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


def build_digest(conn, user_id, day=None, target=TARGET, dry_run=False):
    """Score the pool for one user and lay out their sections.

    dry_run=True skips writing to sent_jobs, so the dashboard can preview a
    digest without burning the jobs it would have shown.
    """
    day = day or db.today_iso()
    pdict = db.get_profile(conn, user_id)
    if not pdict:
        return {"error": "no profile - upload a resume first"}
    profile = profile_from_dict(pdict)

    prior = db.already_sent(conn, user_id)
    first_ever = not prior

    # The pool is local; conn is the account store (D1). Two stores on
    # purpose - see db.jobs_conn().
    rows = _rows_for(db.jobs_conn(), since=_days_ago(POOL_DAYS))
    scored = M.score_many(rows, profile)

    # Everything this user has never been shown. sent_jobs is what stops run
    # four repeating run one, and it is the only per-user state that matters.
    fresh = [m for m in scored if m.job["fp"] not in prior]
    matches = [m for m in fresh if m.is_match]
    near = [m for m in fresh if not m.is_match and m.showable]

    # New since the last delivery vs. the bank held back from earlier days.
    last = conn.execute(
        "SELECT MAX(created_at) c FROM deliveries WHERE user_id=?",
        (user_id,)).fetchone()["c"]
    if last and not first_ever:
        new = [m for m in matches if m.job["first_seen"] >= last]
        reserve = [m for m in matches if m.job["first_seen"] < last]
    else:
        new, reserve = matches, []          # cold start: it is all new

    new.sort(key=lambda m: -m.score)
    reserve.sort(key=lambda m: -m.score)

    picked = new[:target]
    backfilled = 0
    if len(picked) < target:                # thin run - draw on the bank
        take = reserve[:target - len(picked)]
        backfilled = len(take)
        picked += take

    picked.sort(key=lambda m: -m.score)
    chosen_near = sorted(near, key=lambda m: -m.score)[:NEAR_MAX]

    # Stretch used to be drawn straight out of `near`, while `chosen_near` was
    # drawn from the same list with nothing keeping them apart. On a thin run -
    # precisely when stretch fires - the same posting was printed twice: once
    # as a viable "Stretch" and again under "Came close" with the blocker that
    # disqualified it. Worse, `near` is blocked jobs by definition, so a role
    # hiring only in Abu Dhabi was being offered to someone in the Philippines
    # as something to apply for.
    #
    # A stretch is a job you could actually take that scores below the usual
    # bar. Anything with a blocker is not that, it is a near-miss, and it
    # already has a section. So stretch is filled only from unblocked matches
    # that did not make the cut, and never from `near`.
    shown = {m.job["fp"] for m in picked} | {m.job["fp"] for m in chosen_near}
    stretch = []
    if len(picked) < FLOOR:
        spare = [m for m in matches if m.job["fp"] not in shown]
        stretch = sorted(spare, key=lambda m: -m.score)[:FLOOR - len(picked)]

    sections = {
        "strong":       [m for m in picked if m.tier == "strong"],
        "worth_a_look": [m for m in picked if m.tier == "worth_a_look"],
        "stretch":      [m for m in picked if m.tier == "stretch"] + stretch,
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

    thin = len(picked) < FLOOR
    summary = {
        "day": day,
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
        "new_today": len(new),
        "backfilled": backfilled,
        "reserve_left": max(0, len(reserve) - backfilled),
        "first_ever": first_ever,
        "thin": thin,
        "blockers": blockers,
        "blocker_copy": _blocker_copy(blockers),
        "profile": {"level": profile.level, "years": profile.years_experience,
                    "country": profile.home_country,
                    "skills": len(profile.strong_skills)},
    }

    if not dry_run:
        pairs = ([(m.job["fp"], "match") for m in picked]
                 + [(m.job["fp"], "near_miss") for m in chosen_near])
        db.mark_sent(conn, user_id, pairs)
        conn.commit()

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

