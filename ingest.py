# -*- coding: utf-8 -*-
"""
One cleanup round: scrape every board, compare the pool against what the
boards list right now, and tag every posting.

    scrape    every board into freshList.db, wiped first. A board that comes
              back far below its last good count is scraped again, twice at
              most; still short, it sits this round out and its postings keep
              the status they had.
    compare   per board that scraped cleanly, by link:
                listed, already in the pool  -> valid (login_required on a
                                                board flagged for login)
                listed, not in the pool      -> added, same status
                in the pool, not listed      -> unverified, hidden from runs
                                                until verify.py decides
    prune     anything no round has seen or verified for 30 days

verify.py runs right after, in the same n8n workflow (TheJobStash Cleanup),
at boot and every 3 hours. A user's run never scrapes: it scores what is valid
in the pool as it stands.

This is the user-independent half of the pipeline, and keeping it that way is
the whole reason the product scales: one round serves every user.

Two things it does that JobHunt's sweep does not:

  * stores the description, because scoring happens later and per-user
  * fingerprints here rather than relying on sources.py, which returns raw
    rows. The live check found the same Software Architect role five times in
    one fetch, once per timezone variant.

    python ingest.py            all sources
    python ingest.py --fast     JSON APIs only, no Playwright
    python ingest.py --json     the round's report on stdout, log on stderr
"""
import os, re, sys, hashlib, io, json, datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.environ.get("JOBHUNT_DIR", r"D:\AIO Freelance\JobHunt"))

import sources                                    # shared, read-only
import stash_sources                              # the three PH boards, keyword-free
import db, deadrows

# Everything except the three that need a browser or slow HTML scraping.
FAST_SOURCES = ["himalayas", "remoteok", "remotive", "arbeitnow", "jobicy",
                "workingnomads", "themuse", "weworkremotely", "jobspresso",
                "hackernews"]

DESCRIPTION_LIMIT = 3000
# A posting no round has seen or verified for this long is gone; every round
# drops it. Mostly catches boards the verifier cannot get into.
PRUNE_DAYS = 30
# A board is scraped again when it returns less than this share of its last
# good listing, at most RETRIES more times.
SHORT_RATIO = 0.5
RETRIES = 2
# A posting verify.py found alive is not marked unverified again for this
# long. Most JobHunt scrapers read only the first page or two of their board,
# so most of those boards' live jobs are "not listed" every single round.
# ponytail: flat 24h, per-board if one board churns much faster.
RECHECK_HOURS = 24

# What a user's run scores, and what the home page counts.
SCORED = "status IN ('valid','login_required')"

# One cleanup at a time, scrape and verify alike: two at once would double the
# load on the boards and race on the pool file. A round is well under three
# hours, so a lock older than that belongs to one that crashed.
LOCK = os.path.join(HERE, "ingest.lock")
LOCK_STALE_S = 3 * 60 * 60


def norm(s):
    """Normalise for fingerprinting so the same job from two boards groups."""
    s = (s or "").lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"\b(remote|full[- ]?time|part[- ]?time|contract|m/f/d|urgent|"
               r"hiring|timezone restricted)\b", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def fingerprint(job):
    """Company plus title, normalised. Ignores the URL deliberately: it groups
    one role posted to three boards, which are still three pool rows."""
    return hashlib.sha1(
        (norm(job.get("company")) + "|" + norm(job.get("title"))
         ).encode("utf-8")).hexdigest()


def push_pool_stats(total, with_desc):
    """Send the home page its three numbers.

    This is the entire reason the pool ever needed to be reachable from the
    site. poolStats() used to run three aggregates across every row on every
    render of the busiest page; now it reads one row that this writes after
    every round. Best effort: a failed push costs a stale counter on the home
    page, never a round.
    """
    if os.environ.get("JOBSTASH_SKIP_STATS") == "1":
        return                      # a test round against a copy of the pool
    try:
        conn = db.init()
        fresh = db.jobs_conn().execute(
            "SELECT COUNT(*) c FROM jobs WHERE " + SCORED +
            " AND first_seen >= datetime('now','-3 days')").fetchone()["c"]
        srcs = db.jobs_conn().execute(
            "SELECT COUNT(DISTINCT source) c FROM jobs WHERE " + SCORED
        ).fetchone()["c"]
        conn.execute("DELETE FROM pool_stats WHERE id=1")
        conn.execute(
            "INSERT INTO pool_stats (id,pool,fresh,sources,updated_at) "
            "VALUES (1,?,?,?,?)", (total, fresh, srcs, db.now_iso()))
        conn.commit()
        conn.close()
    except Exception as e:                      # noqa: BLE001
        sys.stderr.write("[ingest] pool_stats push failed: %s\n" % e)
    # The public /jobs pages. Its own try: a failure here must not cost the
    # home page its numbers, and stale pages beat missing ones.
    try:
        import pool_pages
        pool_pages.push()
    except Exception as e:                      # noqa: BLE001
        sys.stderr.write("[ingest] pool_pages push failed: %s\n" % e)


def take_lock():
    import time
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


def scrape(fn, last_count):
    """(rows, error, attempts). A failed or short listing is tried again."""
    rows, err, attempt = [], "", 0
    for attempt in range(1, RETRIES + 2):
        try:
            rows, err = fn() or [], ""
        except Exception as e:                  # noqa: BLE001
            rows, err = [], "%s: %s" % (type(e).__name__, e)
        if rows and len(rows) >= (last_count or 0) * SHORT_RATIO:
            return rows, "", attempt
        if rows:
            err = "short: %d listed, last good round had %d" % (
                len(rows), last_count)
        elif not err:
            err = "listed nothing"
    return rows, err, attempt


def _key(url, fp):
    return url or "fp:" + fp


def compare(conn, name, rows, listed_status, now):
    """Tag one board's pool rows against its fresh listing. Returns counts."""
    listed = {}
    for r in rows:
        r["source"] = name
        r["description"] = (r.get("description") or "")[:DESCRIPTION_LIMIT]
        listed.setdefault(_key(r.get("url"), fingerprint(r)), r)
    known = {_key(r["url"], r["fp"]): r for r in conn.execute(
        "SELECT id, url, fp FROM jobs WHERE source=?", (name,))}

    # One role listed several times on the same board (JobHunt's timezone
    # variants): the first link is the posting, the rest are not new rows.
    # A link already in the pool is always updated, never skipped.
    fps_held = {known[k]["fp"] for k in listed if k in known}
    added = dupes = 0
    for key, r in listed.items():
        fp = fingerprint(r)
        if key not in known:
            if fp in fps_held:
                dupes += 1
                continue
            fps_held.add(fp)
        if db.upsert_job(conn, r, fp, listed_status):
            added += 1

    # Everything this board no longer lists, except postings the verifier
    # found alive within RECHECK_HOURS.
    cutoff = (now - datetime.timedelta(hours=RECHECK_HOURS)
              ).strftime("%Y-%m-%dT%H:%M:%SZ")
    missing = [known[k]["id"] for k in known if k not in listed]
    marked = 0
    for i in range(0, len(missing), 500):
        chunk = missing[i:i + 500]
        marked += conn.execute(
            "UPDATE jobs SET status='unverified' WHERE id IN (%s) "
            "AND status != 'unverified' "
            "AND (checked_at IS NULL OR checked_at < ?)"
            % ",".join("?" * len(chunk)), chunk + [cutoff]).rowcount
    return {"listed": len(listed), "new": added, "duplicates": dupes,
            "unverified": marked}


def run(fast=False, verbose=True):
    # The pool is local - see db.jobs_conn(). use_live_store() is still
    # needed so the pool_stats push at the end reaches D1.
    db.use_live_store()
    conn = db.jobs_conn()
    dead = deadrows.connect()
    fresh = deadrows.fresh_connect()
    fresh.execute("DELETE FROM fresh")
    fresh.commit()

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
    login = deadrows.login_boards(dead)
    now = datetime.datetime.now(datetime.timezone.utc)

    totals = {"fetched": 0, "new": 0, "duplicates": 0, "unverified": 0}
    report = []
    for name, fn in picked:
        b = deadrows.board(dead, name)
        rows, err, attempts = scrape(fn, b["last_count"])
        entry = {"name": name, "count": len(rows), "attempts": attempts,
                 "error": err, "skipped": bool(err), "new": 0,
                 "unverified": 0}
        if err:
            deadrows.set_board(dead, name, last_error=err,
                               skipped_at=db.now_iso())
            report.append(entry)
            if verbose:
                print("  %-16s SKIPPED %s" % (name, err))
            continue

        fresh.executemany(
            "INSERT INTO fresh (source,url,fp,title,company) VALUES (?,?,?,?,?)",
            [(name, r.get("url"), fingerprint(r), r.get("title"),
              r.get("company")) for r in rows])
        fresh.commit()
        got = compare(conn, name, rows,
                      "login_required" if name in login else "valid", now)
        conn.commit()
        deadrows.set_board(dead, name, last_count=len(rows),
                           last_ok_at=db.now_iso(), last_error=None)
        entry.update(got)
        report.append(entry)
        totals["fetched"] += len(rows)
        for k in ("new", "duplicates", "unverified"):
            totals[k] += got[k]
        if verbose:
            print("  %-16s %5d listed  %4d new  %4d unverified"
                  % (name, len(rows), got["new"], got["unverified"]))

    # Pruning is part of the round, not a job of its own on a timer.
    stale = [dict(r) for r in conn.execute(
        "SELECT id,url,fp,source,title,company FROM jobs "
        "WHERE last_seen < ?",
        ((now - datetime.timedelta(days=PRUNE_DAYS)
          ).strftime("%Y-%m-%dT%H:%M:%SZ"),))]
    for j in stale:
        deadrows.log_dead(dead, j, "unseen_%dd" % PRUNE_DAYS)
        conn.execute("DELETE FROM jobs WHERE id=?", (j["id"],))
    dead.commit()
    conn.commit()

    counts = {r["status"]: r["n"] for r in conn.execute(
        "SELECT status, COUNT(*) n FROM jobs GROUP BY status")}
    total = conn.execute("SELECT COUNT(*) c FROM jobs WHERE " + SCORED
                         ).fetchone()["c"]
    with_desc = conn.execute(
        "SELECT COUNT(*) c FROM jobs WHERE " + SCORED +
        " AND length(COALESCE(description,''))>0").fetchone()["c"]
    conn.close()

    push_pool_stats(total, with_desc)

    out = dict(totals, pruned=len(stale), pool=total,
               with_description=with_desc, statuses=counts, sources=report)
    deadrows.log_round(dead, "scrape", out)
    dead.close()
    fresh.close()
    return out


if __name__ == "__main__":
    fast = "--fast" in sys.argv
    as_json = "--json" in sys.argv

    # With --json, stdout carries the document and nothing else - the n8n Code
    # node parses it directly, so a stray print here would break the round.
    if as_json:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                      errors="replace")
        log = sys.stderr
    else:
        log = sys.stdout

    if not take_lock():
        print("another cleanup is already running - skipped", file=log)
        if as_json:
            print(json.dumps({"skipped": "already running", "sources": []}))
        raise SystemExit(0)

    print("cleanup round (%s sources)" % ("fast" if fast else "all"), file=log)
    try:
        out = run(fast=fast, verbose=False)
    finally:
        os.unlink(LOCK)

    for s in out["sources"]:
        if s["skipped"]:
            print("  %-16s SKIPPED after %d tries: %s"
                  % (s["name"], s["attempts"], s["error"]), file=log)
        else:
            print("  %-16s %5d listed  %4d new  %4d unverified"
                  % (s["name"], s["count"], s["new"], s["unverified"]), file=log)

    print("", file=log)
    print("  listed           %6d" % out["fetched"], file=log)
    print("  new              %6d" % out["new"], file=log)
    print("  marked unverified%6d" % out["unverified"], file=log)
    print("  pruned           %6d  (unseen %d+ days)" % (out["pruned"], PRUNE_DAYS), file=log)
    print("  scored pool      %6d  (%d with description)"
          % (out["pool"], out["with_description"]), file=log)
    print("  by status        %s" % out["statuses"], file=log)

    if as_json:
        print(json.dumps(out))
