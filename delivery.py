# -*- coding: utf-8 -*-
"""
Turn the shared job pool into one user's digest for one day.

The shape of the problem, from the numbers in JobHunt's own database: a cold
start finds ~75 matches for a narrow profile, then the daily rate settles at
8-13. Sent raw, that reads as 75 then 13 - a cliff, and a cliff reads as "the
app broke". The pool is not actually running out; day one was a backlog and the
rest is the honest steady state, renewed by ~1,000 new rows every day.

So the fix is shape, not volume:

  * cap day one at the same target as every other day and bank the rest
  * backfill thin days from that bank before reaching for anything weaker
  * never send everything held - the reserve is what buys a flat week
  * always carry a "came close" section, on good days too. A section that
    only appears when there is nothing else is a confession; the same section
    every day is a feature.
  * pad with honesty, not filler. Five real matches plus an extra day on the
    plan beats twenty irrelevant ones.

Deliberately NOT 100+ jobs a day. Nobody applies to a hundred jobs, and volume
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

    rows = _rows_for(conn, since=_days_ago(POOL_DAYS))
    scored = M.score_many(rows, profile)

    # Everything this user has never been shown. sent_jobs is what stops day
    # four repeating day one, and it is the only per-user state that matters.
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
    if len(picked) < target:                # thin day - draw on the bank
        take = reserve[:target - len(picked)]
        backfilled = len(take)
        picked += take

    # Only if both are exhausted does the bar come down, and the result is
    # labelled rather than quietly mixed in with the real matches.
    stretch = []
    if len(picked) < FLOOR:
        stretch = [m for m in near if m.score >= profile.min_score // 2][
            :FLOOR - len(picked)]

    picked.sort(key=lambda m: -m.score)
    chosen_near = sorted(near, key=lambda m: -m.score)[:NEAR_MAX]

    sections = {
        "strong":       [m for m in picked if m.tier == "strong"],
        "worth_a_look": [m for m in picked if m.tier == "worth_a_look"],
        "stretch":      [m for m in picked if m.tier == "stretch"] + stretch,
        "near_miss":    chosen_near,
    }

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
        "matches": len(picked),
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


def eligible_users(conn, day=None):
    """Users with an active entitlement who have not been delivered to today."""
    day = day or db.today_iso()
    return [dict(r) for r in conn.execute(
        "SELECT e.*, u.email FROM entitlements e JOIN users u ON u.id=e.user_id "
        "WHERE e.status='active' AND e.starts_on<=? AND e.ends_on>=? "
        "AND NOT EXISTS (SELECT 1 FROM deliveries d WHERE d.user_id=e.user_id "
        "                AND d.day=?)", (day, day, day))]


def extend_entitlement(conn, entitlement_id, days=1):
    """A skipped day is not a delivered day. Extending rather than silently
    consuming it is the difference between a thin week and a refund."""
    conn.execute(
        "UPDATE entitlements SET ends_on=date(ends_on, ?) WHERE id=?",
        ("+%d days" % days, entitlement_id))
    conn.commit()
