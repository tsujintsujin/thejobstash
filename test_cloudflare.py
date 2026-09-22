# -*- coding: utf-8 -*-
"""
Checks for the Cloudflare move.

    python test_cloudflare.py

The whole migration rests on one claim: `d1.Connection` behaves enough like
`sqlite3.Connection` that `matching.py`, `delivery.py` and `run_delivery.py`
did not have to change. This asserts that claim against the real sqlite3,
side by side, rather than trusting it - if the shim ever stops matching, the
symptom otherwise appears as a wrong digest, not an error.

No network. Nothing here talks to Cloudflare.
"""
import datetime, io, json, os, re, sqlite3, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import d1, db, api_bridge

PASS, FAIL = [], []


def check(name, got, want):
    if got == want:
        PASS.append(name)
    else:
        FAIL.append("%s\n     got:  %r\n     want: %r" % (name, got, want))


def section(title):
    print("\n%s\n%s" % (title, "-" * len(title)))


# ---------------------------------------------------------------------------
section("rows and cursors match sqlite3")
# ---------------------------------------------------------------------------
real = sqlite3.connect(":memory:")
real.row_factory = sqlite3.Row
real.execute("CREATE TABLE t (a TEXT, b INTEGER)")
real.execute("INSERT INTO t VALUES ('x', 1)")
real.execute("INSERT INTO t VALUES ('y', 2)")
real_rows = real.execute("SELECT * FROM t ORDER BY b").fetchall()

shim = d1.Cursor([d1.Row({"a": "x", "b": 1}), d1.Row({"a": "y", "b": 2})], 0)
shim_rows = shim.fetchall()

# The three things every caller in this codebase does with a row.
check("row indexed by column name", shim_rows[0]["a"], real_rows[0]["a"])
check("dict(row)", dict(shim_rows[1]), dict(real_rows[1]))
check("set comprehension over a cursor",
      {r["a"] for r in d1.Cursor(shim_rows, 0)},
      {r["a"] for r in real.execute("SELECT * FROM t")})

# `upsert_job` branches on rowcount, so it has to survive the round trip.
check("rowcount carries changes", d1.Cursor([], 3).rowcount, 3)
check("fetchone on an empty result is None", d1.Cursor([], 0).fetchone(), None)
check("fetchone returns the first row", shim.fetchone()["a"], "x")

# ---------------------------------------------------------------------------
section("parameter binding")
# ---------------------------------------------------------------------------
# D1 takes JSON scalars only, so anything sqlite3 would have accepted has to be
# coerced rather than silently serialised as a Python repr.
check("None stays null", d1._bind(None), None)
check("int passes through", d1._bind(7), 7)
check("str passes through", d1._bind("hi"), "hi")
check("bool becomes 0/1 like sqlite3", (d1._bind(True), d1._bind(False)), (1, 0))
check("bytes are decoded", d1._bind(b"ab"), "ab")

# ---------------------------------------------------------------------------
section("the generated D1 migration matches db.py")
# ---------------------------------------------------------------------------
stmts = d1._split(db.SCHEMA.replace("PRAGMA journal_mode=WAL;\n", ""))
tables = [s for s in stmts if s.upper().startswith("CREATE TABLE")]
indexes = [s for s in stmts if s.upper().startswith("CREATE INDEX")]
check("every table is one statement", len(tables), 10)
check("no statement lost its trailing clause",
      all(s.count("(") == s.count(")") for s in stmts), True)
check("indexes survive the split", len(indexes) >= 5, True)

mig = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "web", "migrations", "0001_init.sql")
if os.path.exists(mig):
    sql = io.open(mig, encoding="utf-8").read()
    # The migration is generated from SCHEMA; if someone edits one and not the
    # other, the tables stop matching and D1 silently lacks a column.
    for t in ("jobs", "users", "profiles",
              "deliveries", "trial_runs", "sessions"):
        check("migration creates %s" % t,
              ("CREATE TABLE IF NOT EXISTS %s" % t) in sql, True)
    check("migration keeps google_sub", "google_sub" in sql, True)
    # Credits arrived as a later migration on a live database, so they are
    # checked there rather than in the generated 0001.
    credits_sql = io.open(os.path.join(os.path.dirname(mig), "0003_credits.sql"),
                          encoding="utf-8").read()
    for t in ("payments", "runs"):
        check("credits migration creates %s" % t,
              ("CREATE TABLE IF NOT EXISTS %s" % t) in credits_sql, True)
    check("credits migration drops entitlements",
          "DROP TABLE IF EXISTS entitlements" in credits_sql, True)
    check("every account starts with one credit",
          "credits INTEGER NOT NULL DEFAULT 1" in credits_sql, True)
    check("migration drops the WAL pragma", "journal_mode" not in sql, True)
else:
    FAIL.append("web/migrations/0001_init.sql is missing - run npm run migration:gen")

# ---------------------------------------------------------------------------
section("api_bridge returns instead of exiting")
# ---------------------------------------------------------------------------
# py_server.py calls run() per request. If a command still raised SystemExit
# the server would shut itself down answering one upload.
payload, code = api_bridge.run([])
check("no command is an error, not an exit", (payload["ok"], code), (False, 2))
payload, code = api_bridge.run(["nonsense"])
check("unknown command is an error, not an exit", (payload["ok"], code), (False, 2))
payload, code = api_bridge.run(["stats"])
check("stats still answers", payload["ok"], True)
check("stats counts the pool", payload["pool"] > 0, True)

# The CLI contract the e2e scripts depend on: exactly one JSON object.
check("run() output is JSON-serialisable",
      isinstance(json.dumps(payload, default=str), str), True)

# ---------------------------------------------------------------------------
section("the local path still works")
# ---------------------------------------------------------------------------
# D1 must be opt-in. If `db.init()` ever reached for Cloudflare by default,
# Justin's own JobHunt tooling and every test here would start needing a
# network and a token.
check("D1 is off without env vars", d1.configured(), False)
tmp = os.path.join(tempfile.gettempdir(), "jobstash-test-%d.db" % os.getpid())
try:
    conn = db.init(tmp)
    check("init() still builds a local file", isinstance(conn, sqlite3.Connection), True)
    conn.execute("INSERT INTO users (id,email,created_at) VALUES (?,?,?)",
                 ("usr_test", "a@b.test", db.now_iso()))
    conn.commit()
    row = conn.execute("SELECT email FROM users WHERE id=?", ("usr_test",)).fetchone()
    check("local read-back", row["email"], "a@b.test")
    conn.close()
finally:
    for suffix in ("", "-wal", "-shm"):
        try:
            os.unlink(tmp + suffix)
        except OSError:
            pass

# Passwords must stay verifiable by both sides. lib/db.ts hardcodes the same
# number; workerd refuses PBKDF2 above 100,000, so a value above it here would
# mean every password set by the Python side is unverifiable by the website -
# which looks exactly like "wrong password" and nothing like a bug.
h = db.hash_password("hunter2hunter2")
check("pbkdf2 rounds are within workerd's ceiling", db.PBKDF2_ROUNDS <= 100000, True)
check("pbkdf2 format", h.split("$")[:2], ["pbkdf2", str(db.PBKDF2_ROUNDS)])

ts = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "web", "lib", "db.ts"), encoding="utf-8").read()
m = re.search(r"const ROUNDS = (\d+);", ts)
check("web and python agree on rounds",
      int(m.group(1)) if m else None, db.PBKDF2_ROUNDS)
check("password verifies", db.verify_password("hunter2hunter2", h), True)
check("wrong password refused", db.verify_password("nope", h), False)

# ---------------------------------------------------------------------------
section("a digest is dated in Manila, not UTC")
# ---------------------------------------------------------------------------
# `day` is the label on a Stash row and the name of a downloaded PDF, so it is
# the one value that has to be the user's day rather than UTC's. PH is UTC+8:
# stamped in UTC, every run between midnight and 8am Manila carried yesterday's
# date. Frozen at 23:55Z on the 21st - 7:55am Manila on the 22nd - because that
# is the window where the two disagree, and a test run at any other hour would
# pass either way.
class _FrozenClock(object):
    timezone, timedelta = datetime.timezone, datetime.timedelta

    class datetime(object):
        AT = None

        @staticmethod
        def now(tz=None):
            at = _FrozenClock.datetime.AT
            return at.astimezone(tz) if tz else at


_FrozenClock.datetime.AT = datetime.datetime(
    2026, 9, 21, 23, 55, tzinfo=datetime.timezone.utc)
_real_datetime, db.datetime = db.datetime, _FrozenClock
try:
    check("7:55am Manila is stamped that morning, not the night before",
          db.today_iso(), "2026-09-22")
    # Timestamps stay UTC. Only the user-facing day moved.
    check("now_iso() is still UTC", db.now_iso(), "2026-09-21T23:55:00Z")
finally:
    db.datetime = _real_datetime


# ---------------------------------------------------------------------------
print("\n" + "=" * 68)
for f in FAIL:
    print("FAIL " + f)
print("cloudflare checks: %d passed, %d failed" % (len(PASS), len(FAIL)))
print("=" * 68)
raise SystemExit(1 if FAIL else 0)
