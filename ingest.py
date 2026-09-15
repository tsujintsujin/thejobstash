# -*- coding: utf-8 -*-
"""
Scrape every board once and put the results in the shared pool.

This is the half of the pipeline that is user-independent, and keeping it that
way is the whole reason the product scales: one sweep serves every user,
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
    python ingest.py --age      minutes since the last sweep landed, as JSON
"""
import os, re, sys, hashlib, io, json, datetime, time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.environ.get("JOBHUNT_DIR", r"D:\AIO Freelance\JobHunt"))

import sources                                    # shared, read-only
import stash_sources                              # the three PH boards, keyword-free
import db

# Everything except the three that need a browser or slow HTML scraping.
FAST_SOURCES = ["himalayas", "remoteok", "remotive", "arbeitnow", "jobicy",
                "workingnomads", "themuse", "weworkremotely", "jobspresso",
                "hackernews"]

DESCRIPTION_LIMIT = 3000
# A posting no board has listed for this long is gone; every sweep drops it.
PRUNE_DAYS = 30

# One sweep at a time. Runs arrive whenever users press Run, and two sweeps of
# 13 boards at once would double the load on the boards and race on the pool
# file. An hour is well past the slowest sweep seen, so a lock older than that
# belongs to a sweep that crashed.
LOCK = os.path.join(HERE, "ingest.lock")
LOCK_STALE_S = 60 * 60


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


def push_pool_stats(total, with_desc):
    """Send the home page its three numbers.

    This is the entire reason the pool ever needed to be reachable from the
    site. poolStats() used to run three aggregates across every row on every
    render of the busiest page; now it reads one row that this writes after
    every sweep. Best effort: a failed push costs a stale counter on the home page,
    never an ingest.
    """
    try:
        conn = db.init()
        fresh = db.jobs_conn().execute(
            "SELECT COUNT(*) c FROM jobs "
            "WHERE first_seen >= datetime('now','-3 days')").fetchone()["c"]
        srcs = db.jobs_conn().execute(
            "SELECT COUNT(DISTINCT source) c FROM jobs").fetchone()["c"]
        conn.execute("DELETE FROM pool_stats WHERE id=1")
        conn.execute(
            "INSERT INTO pool_stats (id,pool,fresh,sources,updated_at) "
            "VALUES (1,?,?,?,?)", (total, fresh, srcs, db.now_iso()))
        conn.commit()
        conn.close()
    except Exception as e:                      # noqa: BLE001
        sys.stderr.write("[ingest] pool_stats push failed: %s\n" % e)


def pool_age_minutes():
    """Minutes since the last sweep landed, or None for an empty pool.

    Every sweep stamps last_seen on each job a board still lists and commits
    once at the end, so the newest last_seen is when the last sweep landed.
    """
    t = db.jobs_conn().execute("SELECT MAX(last_seen) t FROM jobs").fetchone()["t"]
    if not t:
        return None
    then = datetime.datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=datetime.timezone.utc)
    now = datetime.datetime.now(datetime.timezone.utc)
    return int((now - then).total_seconds() // 60)


def take_lock():
    try:
        if time.time() - os.path.getmtime(LOCK) > LOCK_STALE_S:
            os.unlink(LOCK)
    except OSError:
        pass
    try:
        os.close(os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        return True
    except FileExistsError:
        return False


def run(fast=False, verbose=True):
    # The pool is local - see db.jobs_conn(). use_live_store() is still
    # needed so the pool_stats push at the end reaches D1, and so anything
    # else this process opens talks to the deployed account store.
    db.use_live_store()
    conn = db.jobs_conn()
    names = FAST_SOURCES if fast else [n for n, _ in sources.ALL_SOURCES]
    # JobStreet skips the per-ad fetch for ads already stored in full. A
    # teaser-only row is a few hundred chars; a fetched ad runs to thousands.
    known = {r["url"] for r in conn.execute(
        "SELECT url FROM jobs WHERE source='jobstreet' "
        "AND length(COALESCE(description,'')) > 800")}
    own = {"kalibrr": stash_sources.kalibrr,
           "onlinejobs": stash_sources.onlinejobs,
           "jobstreet": lambda: stash_sources.jobstreet(known)}
    picked = [(n, own.get(n, fn)) for n, fn in sources.ALL_SOURCES if n in names]

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

    # Pruning is part of the sweep, not a job of its own on a timer. last_seen,
    # not first_seen: a sweep bumps last_seen whenever a board still lists the
    # job, so first_seen would drop postings that are still open.
    pruned = conn.execute(
        "DELETE FROM jobs WHERE last_seen < datetime('now', ?)",
        ("-%d days" % PRUNE_DAYS,)).rowcount
    conn.commit()
    total = conn.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
    with_desc = conn.execute(
        "SELECT COUNT(*) c FROM jobs WHERE length(COALESCE(description,''))>0"
    ).fetchone()["c"]
    conn.close()

    push_pool_stats(total, with_desc)

    return {"fetched": fetched, "new": new, "duplicates": dupes, "pruned": pruned,
            "pool": total, "with_description": with_desc,
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

    if "--age" in sys.argv:
        # What the run workflow asks before deciding whether to sweep first.
        print(json.dumps({"age_minutes": pool_age_minutes(),
                          "running": os.path.exists(LOCK)}))
        raise SystemExit(0)

    if not take_lock():
        # Not an error: the sweep already under way is refreshing the same
        # pool this one would have.
        print("another sweep is already running - skipped", file=log)
        if as_json:
            print(json.dumps({"skipped": "already running", "fetched": 0,
                              "new": 0, "sources": []}))
        raise SystemExit(0)

    print("ingesting (%s sources)" % ("fast" if fast else "all"), file=log)
    try:
        out = run(fast=fast, verbose=False)
    finally:
        os.unlink(LOCK)

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
    print("  pruned           %6d  (unlisted %d+ days)" % (out["pruned"], PRUNE_DAYS), file=log)
    print("  pool total       %6d  (%d with description)"
          % (out["pool"], out["with_description"]), file=log)

    if as_json:
        print(json.dumps(out))
