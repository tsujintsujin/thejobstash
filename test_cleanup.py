# -*- coding: utf-8 -*-
"""
The cleanup round's rules, without a network or a browser.

    python test_cleanup.py

Every failure these catch is silent on the site: a live job quietly deleted,
a dead one quietly shown, or one role printed twice. Runs against temporary
sqlite files, never jobstash.db.
"""
import os, sys, tempfile, shutil, sqlite3, datetime, types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
TMP = tempfile.mkdtemp(prefix="jobstash-cleanup-")
os.environ["JOBSTASH_DB"] = os.path.join(TMP, "jobstash.db")
os.environ["JOBSTASH_USE_D1"] = "0"
os.environ["JOBSTASH_SKIP_STATS"] = "1"

import db, ingest, verify, delivery, deadrows

fails = []


def check(name, got, want):
    ok = got == want
    print("  %-60s %s" % (name, "ok" if ok else "FAIL  got %r want %r" % (got, want)))
    if not ok:
        fails.append(name)


C = verify.classify
JS = "https://ph.jobstreet.com/job/93908553"
HM = "https://himalayas.app/companies/gorin-systems/jobs/full-stack-laravel-react-developer-768830430"
T = "Full Stack Laravel / React Developer"

print("-- the verifier's verdicts")
check("jobstreet closed notice is dead",
      C(JS, "Tester", "", 200, JS, "Sign in This job is no longer advertised", False)[0], "dead")
check("himalayas sending a removed job to /jobs is dead",
      C(HM, T, "Gorin", 200, "https://himalayas.app/jobs", "Remote jobs", False)[0], "dead")
check("a 404 is dead", C(JS, T, "", 404, JS, "", False)[0], "dead")
check("a 403 is refused, not dead", C(HM, T, "", 403, HM, "", False)[0], "refused")
check("a bot check page is refused",
      C(HM, T, "", 200, HM, "Performing security verification", False)[0], "refused")
check("a 503 is retried like a timeout", C(JS, T, "", 503, JS, "", False)[0], "timeout")
check("a live page with the title is alive",
      C(HM, T, "", 200, HM, "Gorin Systems Full Stack Laravel React Developer apply", False)[0], "alive")
check("header 'Sign in' does not make a live page a login wall",
      C(JS, T, "", 200, JS, "Sign in Employer site " + T, False)[0], "alive")
check("jobspresso's 'Position closed? Let us know.' is not a closure",
      C(HM, T, "", 200, HM, T + " Position closed? Let us know.", False)[0], "alive")
check("title words gone is dead",
      C(HM, T, "", 200, HM, "Welcome to our careers page", False)[0], "dead")
check("a login page path is a login wall",
      C(HM, T, "", 200, "https://himalayas.app/login?next=x", "Log in", False)[0], "login")
check("a password form with the job missing is a login wall",
      C(HM, T, "", 200, HM, "Email Password", True)[0], "login")
check("http -> https and host case are not a redirect",
      C("http://remoteOK.com/remote-jobs/x-1137314", "Social Comms", "", 200,
        "https://remoteok.com/remote-jobs/x-1137314/", "social comms role", False)[0], "alive")
check("a changed slug that keeps the id is not a redirect",
      C("https://www.kalibrr.com/c/q/jobs/272255/old", "ReactNative Developer", "", 200,
        "https://www.kalibrr.com/c/q/jobs/272255/new", "ReactNative Developer", False)[0], "alive")
check("a hop to the employer's own site is alive without the title",
      C("https://www.workingnomads.com/job/go/1843239/", "Senior Adobe Commerce Developer", "", 200,
        "https://talent.proxify.io/apply?utm_source=workingnomads",
        "How would you like to start your application? Upload CV", False)[0], "alive")
check("...but a closed notice there is still dead",
      C("https://www.workingnomads.com/job/go/1/", "Growth Marketer", "", 200,
        "https://apply.workable.com/x/j/1/", "This job is no longer available", False)[0], "dead")
check("a same-site hop to a category page is dead",
      C("https://www.workingnomads.com/job/go/1785833/", "Senior Blockchain Developer", "", 200,
        "https://www.workingnomads.com/remote-development-jobs", "Remote Development Jobs", False)[0], "dead")
check("a title of only common words is still checked on its own words",
      C("https://www.onlinejobs.ph/jobseekers/job/it-specialist-1723081", "IT Specialist",
        "onlinejobs-1723081", 200, "https://www.onlinejobs.ph/jobseekers/job/it-specialist-1723081",
        "Back to search results IT Specialist APPLY FOR THIS JOB", False)[0], "alive")
check("title words: at most five, stop words out",
      len(verify.words("Senior Full Stack Laravel React Developer Engineer Remote")) <= 5
      and "senior" not in verify.words("Senior Laravel Developer"), True)

print("\n-- an old pool moves to one row per posting")
old = sqlite3.connect(os.environ["JOBSTASH_DB"])
old.executescript("""
CREATE TABLE jobs (fp TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT NOT NULL,
  company TEXT, location TEXT, url TEXT, salary TEXT, seniority TEXT, posted TEXT,
  description TEXT, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL);
""")
now = db.now_iso()
old.execute("INSERT INTO jobs VALUES ('fpA','himalayas','Role A','Co','','https://h/a','','','','d',?,?)", (now, now))
old.execute("INSERT INTO jobs VALUES ('fpB','jobstreet','Role B','Co','','https://j/b','','','','d',?,?)", (now, now))
old.commit(); old.close()
conn = db.jobs_conn()
cols = {r["name"] for r in conn.execute("PRAGMA table_info(jobs)")}
check("rebuilt with id, status and checked_at", {"id", "status", "checked_at"} <= cols, True)
check("every old row kept, as valid",
      [r[0] for r in conn.execute("SELECT status FROM jobs ORDER BY fp")], ["valid", "valid"])
conn.close()
conn = db.jobs_conn()           # opening it again must not rebuild again
check("a second open is a no-op", conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 2)
conn.execute("DELETE FROM jobs")
conn.commit()

print("\n-- compare")
def row(title, url, company="Acme"):
    return {"title": title, "company": company, "url": url, "description": "x"}

when = datetime.datetime.now(datetime.timezone.utc)
got = ingest.compare(conn, "b1", [row("Dev", "https://b1/1"), row("QA", "https://b1/2")], "valid", when)
check("a new listing is added", got["new"], 2)
got = ingest.compare(conn, "b1", [row("Dev", "https://b1/1")], "valid", when)
st = dict(conn.execute("SELECT url, status FROM jobs WHERE source='b1'").fetchall())
check("a posting the board dropped is unverified", st["https://b1/2"], "unverified")
check("a posting still listed stays valid", st["https://b1/1"], "valid")
ingest.compare(conn, "b1", [row("Dev", "https://b1/1"), row("QA", "https://b1/2")], "valid", when)
check("listed again is valid again",
      conn.execute("SELECT status FROM jobs WHERE url='https://b1/2'").fetchone()[0], "valid")

conn.execute("UPDATE jobs SET checked_at=? WHERE url='https://b1/2'", (db.now_iso(),))
ingest.compare(conn, "b1", [row("Dev", "https://b1/1")], "valid", when)
check("verified alive lately: not re-marked",
      conn.execute("SELECT status FROM jobs WHERE url='https://b1/2'").fetchone()[0], "valid")

ingest.compare(conn, "b2", [row("Dev", "https://b2/1")], "valid", when)
check("the same role on another board is its own row",
      conn.execute("SELECT COUNT(*) FROM jobs WHERE title='Dev'").fetchone()[0], 2)
got = ingest.compare(conn, "b2", [row("Dev", "https://b2/1"), row("Dev", "https://b2/1-tz")],
                     "valid", when)
check("a role listed twice on one board is not added twice", got["duplicates"], 1)
ingest.compare(conn, "b3", [row("Gated", "https://b3/1")], "login_required", when)
check("a login board's listing is login_required",
      conn.execute("SELECT status FROM jobs WHERE source='b3'").fetchone()[0], "login_required")

print("\n-- scrape retries")
calls = []
def flaky():
    calls.append(1)
    return [] if len(calls) < 2 else [row("x", "u")] * 10
rows, err, n = ingest.scrape(flaky, 10)
check("an empty listing is scraped again", (len(rows), err, n), (10, "", 2))
rows, err, n = ingest.scrape(lambda: [row("x", "u")] * 3, 10)
check("still short after two retries: skipped", (bool(err), n), (True, 3))
def boom():
    raise RuntimeError("down")
check("a board that errors is skipped", bool(ingest.scrape(boom, None)[1]), True)
check("a first-ever round only needs something",
      ingest.scrape(lambda: [row("x", "u")], None)[1], "")

print("\n-- the digest shows each role once, and never an unverified one")
conn.execute("UPDATE jobs SET status='unverified' WHERE source='b1'")
conn.commit()
rows = delivery._rows_for(conn)
check("unverified rows are not scored", any(r["source"] == "b1" for r in rows), False)
M = lambda job, score, match=True: types.SimpleNamespace(job=job, score=score, is_match=match)
a = M({"fp": "f", "status": "login_required"}, 70)
b = M({"fp": "f", "status": "valid"}, 70)
c = M({"fp": "f", "status": "valid"}, 40, match=False)
check("same score: the link without a login wins", delivery._one_per_job([a, b, c]), [b])
d = M({"fp": "g", "status": "login_required"}, 80)
e = M({"fp": "g", "status": "valid"}, 60)
check("otherwise the better posting wins", delivery._one_per_job([e, d]), [d])

print("\n-- a board's batch")
import asyncio
dead = deadrows.connect()
verify.DELAY_S = 0


class FakeCtx:
    async def new_page(self):
        return None

    async def close(self):
        pass


class FakeBrowser:
    async def new_context(self, **kw):
        return FakeCtx()


def batch(name, verdicts):
    """Run board_round over postings whose check() answers are scripted."""
    conn.execute("DELETE FROM jobs WHERE source=?", (name,))
    jobs = []
    for i, v in enumerate(verdicts):
        r = row("Job %d" % i, "https://%s/%d" % (name, i))
        r["source"] = name
        db.upsert_job(conn, r, "fp%s%d" % (name, i), "unverified")
        jobs.append(dict(conn.execute(
            "SELECT id,url,fp,source,title,company FROM jobs WHERE url=?",
            (r["url"],)).fetchone()))
    answers = iter(verdicts)

    async def fake_check(page, job):
        return next(answers), "scripted", 200, job["url"]
    verify.check = fake_check
    rep = asyncio.run(verify.board_round(FakeBrowser(), name, jobs, conn, dead))
    left = conn.execute("SELECT COUNT(*) FROM jobs WHERE source=?", (name,)).fetchone()[0]
    return rep, left

rep, left = batch("wwr", ["dead"] + ["refused"] * 18)
check("mostly refused after a first answer: board blocked", rep["blocked"], True)
check("  and only the dead posting is deleted", (rep["deleted"], left), (1, 18))
rep, left = batch("hm", ["refused"] * 5)
check("refused from the first page: blocked, stops after 3", (rep["blocked"], rep["checked"]), (True, 3))
check("  and nothing is deleted", left, 5)
rep, left = batch("ok", ["alive"] * 9 + ["refused"])
check("one refusal on an open board is a dead posting", (rep["blocked"], rep["deleted"], left), (False, 1, 9))
check("  and the live ones are valid again",
      conn.execute("SELECT COUNT(*) FROM jobs WHERE source='ok' AND status='valid' "
                   "AND checked_at IS NOT NULL").fetchone()[0], 9)
rep, left = batch("lg", ["login", "login", "alive"])
check("two login walls: login board, unlisted postings deleted",
      (rep["login"], left, deadrows.board(dead, "lg")["login_required"]), (True, 0, 1))
rep, left = batch("one", ["login", "alive"])
check("a single login wall is a dead posting", (rep["login"], left), (False, 1))

print("\n-- deadRowsDb")
deadrows.set_board(dead, "b3", login_required=1)
check("login boards are remembered", "b3" in deadrows.login_boards(dead), True)
deadrows.log_dead(dead, {"url": "u", "source": "b1"}, "says: closed")
dead.commit()
check("a deletion is logged", dead.execute("SELECT reason FROM dead_rows WHERE url='u'").fetchone()[0],
      "says: closed")
check("it sits next to the pool", os.path.exists(os.path.join(TMP, "deadRowsDb.db")), True)

conn.close(); dead.close()
shutil.rmtree(TMP, ignore_errors=True)
print("\ncleanup checks: %d failed" % len(fails))
raise SystemExit(1 if fails else 0)
