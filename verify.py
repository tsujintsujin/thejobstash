# -*- coding: utf-8 -*-
"""
The verifier: open every posting ingest.py marked unverified, decide if it is
still up, and delete it if it is not.

Runs right after ingest.py in the cleanup workflow. A posting is unverified
because its board stopped listing it - usually because it closed, sometimes
only because the scraper reads the first page or two of a big board. This is
what tells the two apart, in a real (headless) browser so pages that draw
themselves with JavaScript are read after they have drawn.

    alive     loads, still carries the job's title words (or hops to the
              employer's own site), no closed notice
                -> valid again, and left alone for RECHECK_HOURS
    dead      404/410, a closed notice, sent somewhere else on the same site,
              or the title words are gone                     -> deleted
    timeout   tried 3 times                                   -> deleted
    refused   403/429/bot check, tried 3 times, slower        -> deleted
              ...unless the board refuses its first 3 pages or half its
              batch: then the board is flagged blocked and no refused posting
              of it is deleted (weworkremotely refuses live pages too)
    login     2 postings in a row behind a login page -> the board is flagged
              login_required; what it still lists shows with a label, what it
              no longer lists is deleted

Every deletion is written to deadRowsDb with its reason (`python deadrows.py`).

    python verify.py [--json] [--limit N] [--board NAME]
"""
import os, re, sys, json, math, asyncio, datetime, io
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ingest, db, deadrows                     # ingest wraps stdout for utf-8
from sources import UA

# ponytail: one flat cap and delay for every board. A round of 800 at ~3s is
# ~40 min per board, boards run side by side; per-board numbers if one board
# needs gentler handling.
PER_BOARD_MAX = 800
DELAY_S = 1.5              # between two pages of the same board
TRIES = 3                  # the first attempt plus two retries
RETRY_WAIT_S = {"timeout": 3, "refused": 10}
BLOCK_PROBE = 3            # this many refusals in a row, first thing: blocked
BLOCKED_SHARE = 0.5        # or refused on at least this share of the batch
LOGIN_CONFIRM = 2          # this many login walls in a row: login board
WORD_SHARE = 0.6           # of the title's words that must still be on the page

# Exact phrases only. Single words are not enough: jobspresso prints
# "Position closed? Let us know." on every live posting, and every board's
# header says "Sign in".
DEAD_PHRASES = (
    "this job is no longer advertised",          # jobstreet
    "no longer accepting applications",
    "job is no longer available",
    "position is no longer available",
    "posting is no longer available",
    "listing is no longer available",
    "job is no longer active",
    "listing is no longer active",
    "this job has expired",
    "job posting has expired",
    "job listing has expired",
    "this job is closed",
    "this job has been closed",
    "job has been removed",
    "position has been filled",
    "this job has been filled",
    "job not found",
    "page not found",
)
REFUSED_PHRASES = ("performing security verification", "verify you are human",
                   "checking your browser", "attention required")
LOGIN_PATH = re.compile(r"/(log-?in|sign-?in|sign_in|signin|auth|sso)(/|$|\?)", re.I)
STOP = set("the and for with from you your our are job jobs role remote hiring "
           "full part time senior junior mid level lead manager specialist "
           "position opening work based".split())


def words(title, company=""):
    """Up to five words that should still be on a live posting's page.

    A title made only of short or common words ("IT Specialist") keeps them
    all rather than borrowing the company: onlinejobs' company is a
    placeholder that never appears on the page, and borrowing it deleted live
    postings in the first real round.
    """
    every = [t for t in re.findall(r"[a-z0-9]+", (title or "").lower())
             if len(t) > 1]
    toks = [t for t in every if len(t) > 2 and t not in STOP]
    if len(toks) < 2:
        toks = every
    seen, out = set(), []
    for t in sorted(toks, key=len, reverse=True):
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:5]


def _site(u):
    return (urlsplit(u).hostname or "").lower().removeprefix("www.")


def _path(u):
    return urlsplit(u).path.rstrip("/").lower()


def classify(url, title, company, status, final_url, text, has_password):
    """(verdict, reason). verdict: alive | dead | timeout | refused | login.

    Pure, so test_cleanup.py can hold it to the rules without a browser.
    """
    low = " ".join((text or "").lower().split())
    if status in (401, 403, 429) or any(p in low for p in REFUSED_PHRASES):
        return "refused", "http_%s" % status
    if status in (404, 410):
        return "dead", "http_%s" % status
    if status and status >= 500:
        return "timeout", "http_%s" % status
    for p in DEAD_PHRASES:
        if p in low:
            return "dead", "says: " + p
    if final_url and LOGIN_PATH.search(urlsplit(final_url).path or ""):
        return "login", "login page"

    # A hop to another site is the employer's own application page
    # (workingnomads -> Workable, Proxify). Those often never repeat the
    # title - Proxify's is a bare "upload your CV" form - so only a status or
    # a closed notice above can call one dead.
    if final_url and _site(final_url) != _site(url):
        return "alive", "employer site"

    # Sent elsewhere on the same site, to a page that is not this posting:
    # himalayas answers a removed job with its /jobs index. A redirect that
    # keeps the job's id (a changed slug, http -> https, a trailing slash) is
    # not a closure.
    if final_url and _path(final_url) != _path(url):
        ids = re.findall(r"\d{4,}", urlsplit(url).path)
        tail = _path(url).rsplit("/", 1)[-1]
        if not any(i in final_url for i in ids) and tail not in _path(final_url):
            return "dead", "redirected to " + (_path(final_url) or "/")

    want = words(title, company)
    got = sum(1 for w in want if w in low)
    if want and got < math.ceil(len(want) * WORD_SHARE):
        if has_password:
            return "login", "login form, job words missing"
        return "dead", "job words missing (%d of %d)" % (got, len(want))
    return "alive", "ok"


async def check(page, job):
    """One page, retried. (verdict, reason, status, final_url)."""
    verdict = reason = final = None
    status = None
    for attempt in range(TRIES):
        try:
            resp = await page.goto(job["url"], wait_until="domcontentloaded",
                                   timeout=25000)
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:                   # noqa: BLE001
                pass                            # busy pages never go idle
            status = resp.status if resp else 200
            final = page.url
            text = await page.inner_text("body")
            pw = await page.locator("input[type=password]").count() > 0
            verdict, reason = classify(job["url"], job["title"], job["company"],
                                       status, final, text, pw)
        except Exception as e:                  # noqa: BLE001
            verdict, reason = "timeout", type(e).__name__
        if verdict not in RETRY_WAIT_S or attempt == TRIES - 1:
            break
        await asyncio.sleep(RETRY_WAIT_S[verdict])
    return verdict, reason, status, final


async def board_round(browser, name, jobs, conn, dead):
    """Verify one board's unverified postings. Returns its report."""
    rep = {"board": name, "queued": len(jobs), "checked": 0, "alive": 0,
           "deleted": 0, "reasons": {}, "blocked": False, "login": False,
           "left": 0}

    def drop(job, reason, status=None, final=None):
        deadrows.log_dead(dead, job, reason, status, final)
        conn.execute("DELETE FROM jobs WHERE id=?", (job["id"],))
        rep["deleted"] += 1
        rep["reasons"][reason.split(" (")[0]] = \
            rep["reasons"].get(reason.split(" (")[0], 0) + 1

    if deadrows.board(dead, name)["login_required"]:
        # Behind a login and no longer listed: nothing to open, nothing to
        # show. What the board still lists was tagged by ingest.py.
        for j in jobs:
            drop(j, "login board, no longer listed")
        return rep

    batch, rep["left"] = jobs[:PER_BOARD_MAX], max(0, len(jobs) - PER_BOARD_MAX)
    ctx = await browser.new_context(user_agent=UA)
    page = await ctx.new_page()
    login_run = 0
    # Refusals are held until the whole batch is in. weworkremotely refuses a
    # headless browser on live postings as well as dead ones, so a board that
    # mostly refuses says nothing about its jobs - only a refusal from a board
    # that otherwise lets us in is a posting-level answer.
    refused = []

    def blocked():
        rep["blocked"] = True
        deadrows.set_board(dead, name, blocked_at=db.now_iso())

    try:
        for n, job in enumerate(batch):
            if n:
                await asyncio.sleep(DELAY_S)
            verdict, reason, status, final = await check(page, job)
            rep["checked"] += 1

            if verdict == "refused":
                refused.append((job, "refused after %d tries (%s)" % (TRIES, reason),
                                status, final))
                if len(refused) == n + 1 >= min(BLOCK_PROBE, len(batch)):
                    blocked()           # refused from the first page: stop
                    return rep
                continue

            if verdict == "login":
                login_run += 1
                held_login = (job, reason, status, final)
                if login_run >= LOGIN_CONFIRM:
                    rep["login"] = True
                    deadrows.set_board(dead, name, login_required=1,
                                       login_at=db.now_iso())
                    for j in batch[n - LOGIN_CONFIRM + 1:]:
                        drop(j, "login board, no longer listed")
                    rep["left"] = 0
                    for j in jobs[PER_BOARD_MAX:]:
                        drop(j, "login board, no longer listed")
                    return rep
                continue
            if login_run:               # one login page, then a real one
                drop(*held_login)
                login_run = 0

            if verdict == "alive":
                conn.execute(
                    "UPDATE jobs SET status='valid', checked_at=?, last_seen=? "
                    "WHERE id=?", (db.now_iso(), db.now_iso(), job["id"]))
                rep["alive"] += 1
            else:
                drop(job, reason if verdict == "dead" else
                     "%s after %d tries (%s)" % (verdict, TRIES, reason),
                     status, final)
            if n % 20 == 0:
                conn.commit()
                dead.commit()
        if login_run:
            drop(*held_login)
        if refused and len(refused) >= rep["checked"] * BLOCKED_SHARE:
            blocked()
        else:
            for r in refused:
                drop(*r)
    finally:
        conn.commit()
        dead.commit()
        await ctx.close()
    return rep


async def main(limit=None, only=None):
    from playwright.async_api import async_playwright
    conn = db.jobs_conn()
    dead = deadrows.connect()
    q = ("SELECT id,url,fp,source,title,company FROM jobs "
         "WHERE status='unverified' ORDER BY last_seen")
    queue = {}
    for r in conn.execute(q):
        if only and r["source"] != only:
            continue
        queue.setdefault(r["source"], []).append(dict(r))
    if limit:
        queue = {k: v[:limit] for k, v in queue.items()}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            boards = await asyncio.gather(*(
                board_round(browser, name, jobs, conn, dead)
                for name, jobs in sorted(queue.items())))
        finally:
            await browser.close()

    total = conn.execute("SELECT COUNT(*) c FROM jobs WHERE " + ingest.SCORED
                         ).fetchone()["c"]
    with_desc = conn.execute(
        "SELECT COUNT(*) c FROM jobs WHERE " + ingest.SCORED +
        " AND length(COALESCE(description,''))>0").fetchone()["c"]
    waiting = conn.execute(
        "SELECT COUNT(*) c FROM jobs WHERE status='unverified'").fetchone()["c"]
    conn.close()
    ingest.push_pool_stats(total, with_desc)

    out = {"checked": sum(b["checked"] for b in boards),
           "alive": sum(b["alive"] for b in boards),
           "deleted": sum(b["deleted"] for b in boards),
           "still_unverified": waiting, "pool": total,
           "blocked_boards": [b["board"] for b in boards if b["blocked"]],
           "login_boards": [b["board"] for b in boards if b["login"]],
           "boards": boards}
    deadrows.log_round(dead, "verify", out)
    dead.close()
    return out


if __name__ == "__main__":
    as_json = "--json" in sys.argv
    arg = lambda k: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else None
    log = sys.stderr if as_json else sys.stdout
    if as_json:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                      errors="replace")
        log = sys.stderr

    if not ingest.take_lock():
        print("a cleanup is already running - skipped", file=log)
        if as_json:
            print(json.dumps({"skipped": "already running", "boards": []}))
        raise SystemExit(0)
    try:
        out = asyncio.run(main(limit=int(arg("--limit") or 0) or None,
                               only=arg("--board")))
    finally:
        os.unlink(ingest.LOCK)

    for b in out["boards"]:
        flag = " BLOCKED" if b["blocked"] else (" LOGIN" if b["login"] else "")
        print("  %-16s %4d queued %4d checked %4d alive %4d deleted %4d left%s"
              % (b["board"], b["queued"], b["checked"], b["alive"],
                 b["deleted"], b["left"], flag), file=log)
        for r, c in sorted(b["reasons"].items(), key=lambda kv: -kv[1]):
            print("  %16s   %5d  %s" % ("", c, r), file=log)
    print("\n  deleted %d · alive %d · still unverified %d · scored pool %d"
          % (out["deleted"], out["alive"], out["still_unverified"],
             out["pool"]), file=log)
    if as_json:
        print(json.dumps(out))
