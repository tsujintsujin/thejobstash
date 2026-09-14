"""Score a resume file against the live pool and print what comes back.

The instrument for PLAN-REBUILD.md. Every phase is judged by the same
question - did the job list get better? - so that question needs an answer in
one command, offline, without the site, without sending mail, and without
consuming anything.

    python bench.py "Resumes/testing samples/Jecery_Masiga_Resume_1.docx"
    python bench.py <resume> --json        machine-readable, for diffing
    python bench.py <resume> --db jobstash.db    force the local pool

Reuses db.init(), delivery._rows_for() and matching.score_many() rather than
reimplementing any of it, so what this prints is what a real digest would see.
Nothing is written: no sent_jobs, no deliveries, no profile row.
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import db, delivery, matching, resume_parse  # noqa: E402

# db.init() loads .env.cloudflare itself now, but _d1_on() below reports which
# pool was used and is read before init() runs in --json mode.
db.load_env()


def _safe(s):
    """Windows consoles are cp1252; scraped job titles are not."""
    return (s or "").encode(sys.stdout.encoding or "utf-8",
                            "replace").decode(sys.stdout.encoding or "utf-8")


def _pool_label(db_path):
    """The pool is local by design now - see db.jobs_conn()."""
    import db as _db
    return "local sqlite: %s" % os.path.basename(db_path or _db.DB_PATH)


def run(path, db_path=None, pool_days=delivery.POOL_DAYS):
    text = resume_parse.extract_text(path)
    if text.startswith("__PARSE_ERROR__"):
        raise SystemExit("could not read %s: %s" % (path, text))

    profile, diag = resume_parse.parse_profile(text)

    # Local pool - no Worker round trip. Reading 2,199 rows with
    # descriptions through the site is what took production down.
    conn = db.jobs_conn(db_path)
    rows = delivery._rows_for(conn, since=delivery._days_ago(pool_days))
    scored = matching.score_many(rows, profile)

    matches = [m for m in scored if m.is_match]
    near = [m for m in scored if not m.is_match and m.showable]
    hidden = [m for m in scored if not m.is_match and not m.showable]

    # Why the rest never reached the scorer at all - role family excludes
    # outright, and that is the single biggest bucket for a non-dev resume.
    blocker_tally = {}
    for m in near + hidden:
        for k in m.blocker_kinds:
            blocker_tally[k] = blocker_tally.get(k, 0) + 1

    return {
        "resume": os.path.basename(path),
        "pool": _pool_label(db_path),
        "pool_total": len(rows),
        "scored": len(scored),
        "unscored_wrong_family": len(rows) - len(scored),
        "matches": len(matches),
        "near_misses": len(near),
        "hidden": len(hidden),
        "blockers": dict(sorted(blocker_tally.items(),
                                key=lambda kv: -kv[1])),
        "profile": {
            "families": diag["families"],
            "family_scores": diag["family_scores"],
            "skills_found": diag["skills_found"],
            "top_skills": diag["top_skills"],
            "years": diag["years"],
            "total_years": diag["total_years"],
            "level": diag["level"],
            "country": diag["country"],
            "text_chars": diag["text_chars"],
            "thin": diag["thin"],
            "min_skill_hits": profile.min_skill_hits,
            "remote_only": profile.remote_only,
            "wants_local_onsite": profile.wants_local_onsite,
        },
        "_matches": matches,
        "_near": near,
    }


def _line(m):
    loc = _safe(m.job.get("location") or "-")[:28]
    return "  %5.1f  %-46s %-24s %s" % (
        m.score, _safe(m.job["title"])[:46], loc,
        ", ".join(m.blocker_kinds) or "clean")


def report(r, top=15):
    p = r["profile"]
    print("=" * 78)
    print(_safe(r["resume"]))
    print("=" * 78)
    print("PROFILE")
    print("  families      %s   %s" % (p["families"], p["family_scores"]))
    print("  skills        %d   %s" % (p["skills_found"], p["top_skills"][:10]))
    print("  years         relevant=%s total=%s -> level %s"
          % (p["years"], p["total_years"], p["level"]))
    print("  country       %s" % p["country"])
    print("  work setup    remote_only=%s wants_local_onsite=%s"
          % (p["remote_only"], p["wants_local_onsite"]))
    print("  min_skill_hits %d | chars %d | thin=%s"
          % (p["min_skill_hits"], p["text_chars"], p["thin"]))
    print()
    print("POOL  [%s]" % r["pool"])
    print("  %d total  ->  %d scored  |  %d never scored (wrong role family)"
          % (r["pool_total"], r["scored"], r["unscored_wrong_family"]))
    print("  %d matches  |  %d near-misses shown-able  |  %d hidden"
          % (r["matches"], r["near_misses"], r["hidden"]))
    print("  blockers: %s" % r["blockers"])
    print()
    print("TOP MATCHES")
    for m in r["_matches"][:top]:
        print(_line(m))
    if not r["_matches"]:
        print("  (none)")
    print()
    print("TOP NEAR-MISSES")
    for m in sorted(r["_near"], key=lambda m: -m.score)[:top]:
        print(_line(m))
    if not r["_near"]:
        print("  (none)")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("resume")
    ap.add_argument("--db", default=None,
                    help="force a sqlite file instead of D1")
    ap.add_argument("--days", type=int, default=delivery.POOL_DAYS)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    r = run(a.resume, a.db, a.days)
    if a.json:
        r.pop("_matches"), r.pop("_near")
        print(json.dumps(r, indent=1, default=str))
    else:
        report(r, a.top)


if __name__ == "__main__":
    main()
