# -*- coding: utf-8 -*-
"""
Scrape every board once and put the results in the shared pool.

This is the half of the pipeline that is user-independent, and keeping it that
way is the whole reason the product scales: one sweep serves every subscriber,
so the marginal cost of the five-hundredth user is a SQL query rather than
another thirteen HTTP crawls.

Two things it does that JobHunt's sweep does not:

  * stores the description, because scoring now happens later and per-user
  * fingerprints here rather than relying on sources.py, which returns raw
    rows. The live check found the same Software Architect role five times in
    one fetch, once per timezone variant. sources.py does not dedupe - JobHunt
    gets away with it because its own INSERT is keyed on the fingerprint.

    python ingest.py            all sources
    python ingest.py --fast     JSON APIs only, no Playwright
"""
import os, re, sys, hashlib, io, json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.environ.get("JOBHUNT_DIR", r"D:\AIO Freelance\JobHunt"))

import sources                                    # shared, read-only
import db

# Everything except the three that need a browser or slow HTML scraping.
FAST_SOURCES = ["himalayas", "remoteok", "remotive", "arbeitnow", "jobicy",
                "workingnomads", "themuse", "weworkremotely", "jobspresso",
                "hackernews"]

DESCRIPTION_LIMIT = 3000        # ~180MB/year at 1k jobs/day with 60-day pruning
RETENTION_DAYS = 60


def norm(s):
    """Normalise for fingerprinting so the same job from two boards collapses."""
    s = (s or "").lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"\b(remote|full[- ]?time|part[- ]?time|contract|m/f/d|urgent|"
               r"hiring|timezone restricted)\b", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def fingerprint(job):
    """Company plus title, normalised. Ignores the URL deliberately, so one
    role posted to three boards is stored once."""
    return hashlib.sha1(
        (norm(job.get("company")) + "|" + norm(job.get("title"))
         ).encode("utf-8")).hexdigest()


def prune(conn, days=RETENTION_DAYS):
    """Job adverts older than two months are dead. Keeping them costs storage
    and would let a stale posting reach a paying user."""
    cur = conn.execute(
        "DELETE FROM jobs WHERE last_seen < datetime('now', ?)",
        ("-%d days" % days,))
    return cur.rowcount


def run(fast=False, verbose=True):
    conn = db.init()
    names = FAST_SOURCES if fast else [n for n, _ in sources.ALL_SOURCES]
    picked = [(n, fn) for n, fn in sources.ALL_SOURCES if n in names]

    fetched = new = dupes = 0
    report = []
    for name, fn in picked:
        try:
            rows = fn()
        except Exception as e:
            report.append({"name": name, "count": 0,
                           "error": "%s: %s" % (type(e).__name__, e)})
            if verbose:
                print("  %-16s FAILED %s" % (name, type(e).__name__))
            continue

        seen_here = set()
        added = 0
        for r in rows:
            fp = fingerprint(r)
            if fp in seen_here:            # duplicate inside this one board
                dupes += 1
                continue
            seen_here.add(fp)
            r["source"] = name
            r["description"] = (r.get("description") or "")[:DESCRIPTION_LIMIT]
            if db.upsert_job(conn, r, fp):
                added += 1
            else:
                dupes += 1
        fetched += len(rows)
        new += added
        report.append({"name": name, "count": len(rows), "new": added,
                       "error": ""})
        if verbose:
            print("  %-16s %5d fetched  %4d new" % (name, len(rows), added))

    conn.commit()
    removed = prune(conn)
    conn.commit()
    total = conn.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
    with_desc = conn.execute(
        "SELECT COUNT(*) c FROM jobs WHERE length(COALESCE(description,''))>0"
    ).fetchone()["c"]
    conn.close()

    return {"fetched": fetched, "new": new, "duplicates": dupes,
            "pruned": removed, "pool": total, "with_description": with_desc,
            "sources": report}


if __name__ == "__main__":
    fast = "--fast" in sys.argv
    as_json = "--json" in sys.argv

    # With --json, stdout carries the document and nothing else - the n8n Code
    # node parses it directly, so a stray print here would break the run. The
    # human log goes to stderr, matching the convention JobHunt already uses.
    if as_json:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                      errors="replace")
        log = sys.stderr
    else:
        log = sys.stdout

    print("ingesting (%s sources)" % ("fast" if fast else "all"), file=log)
    out = run(fast=fast, verbose=False)

    for s in out["sources"]:
        if s["error"]:
            print("  %-16s FAILED %s" % (s["name"], s["error"]), file=log)
        else:
            print("  %-16s %5d fetched  %4d new"
                  % (s["name"], s["count"], s["new"]), file=log)

    print("", file=log)
    print("  fetched          %6d" % out["fetched"], file=log)
    print("  new              %6d" % out["new"], file=log)
    print("  duplicates       %6d" % out["duplicates"], file=log)
    print("  pruned (>60d)    %6d" % out["pruned"], file=log)
    print("  pool total       %6d  (%d with description)"
          % (out["pool"], out["with_description"]), file=log)

    if as_json:
        print(json.dumps(out))
