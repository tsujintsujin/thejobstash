# -*- coding: utf-8 -*-
"""
Storage for TheJobStash.

SQLite for now, deliberately written so the move to Supabase/Postgres is a
connection-string change and not a rewrite:

  * no SQLite-only types - TEXT/INTEGER/REAL only
  * every timestamp is an ISO-8601 UTC string, not a SQLite datetime
  * booleans are INTEGER 0/1
  * no AUTOINCREMENT anywhere - ids are generated in Python, so rows can be
    inserted from either the Python worker or the web app without a sequence

WAL is on because two processes touch this file: the Python worker writes jobs
and deliveries, the Next.js app reads them and writes users.

The four tables are the ones the architecture discussion settled on:

  jobs          the shared pool, scraped once, read by every user
  profiles      one per user - the thing JobHunt/profile.py hard-codes
  entitlements  a paid (or, for now, free) window of daily deliveries
  sent_jobs     what each user has already been shown, so day 4 never repeats
                day 1. This is the only piece JobHunt has no equivalent of.
"""
import os, sqlite3, json, hashlib, secrets, datetime

import d1

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("JOBSTASH_DB", os.path.join(HERE, "jobstash.db"))


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def today_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def new_id(prefix=""):
    return prefix + secrets.token_hex(8)


SCHEMA = """
PRAGMA journal_mode=WAL;

-- The shared pool. Scraped once per day regardless of how many users exist;
-- this is what makes the marginal cost of user 500 the same as user 1.
CREATE TABLE IF NOT EXISTS jobs (
    fp            TEXT PRIMARY KEY,     -- normalised company+title hash
    source        TEXT NOT NULL,
    title         TEXT NOT NULL,
    company       TEXT,
    location      TEXT,
    url           TEXT,
    salary        TEXT,
    seniority     TEXT,
    posted        TEXT,
    -- JobHunt throws this away after scoring. Storing it is what allows a user
    -- who signs up today to be scored against jobs scraped last week.
    description   TEXT,
    first_seen    TEXT NOT NULL,
    last_seen     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen);
CREATE INDEX IF NOT EXISTS idx_jobs_source     ON jobs(source);

CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT,                 -- NULL when the account is OAuth-only
    -- Google's stable subject id. Not the email: Google lets people change
    -- theirs, and matching on an address that moved would hand one person's
    -- stash to whoever inherited it.
    google_sub    TEXT UNIQUE,
    created_at    TEXT NOT NULL
);

-- One user's matching rules. profile_json is a serialised profiles.Profile.
CREATE TABLE IF NOT EXISTS profiles (
    user_id       TEXT PRIMARY KEY REFERENCES users(id),
    resume_name   TEXT,
    resume_text   TEXT,
    profile_json  TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

-- A window of daily deliveries. Payment is switched off, so these are granted
-- free at signup; when Stripe lands it writes exactly the same row.
CREATE TABLE IF NOT EXISTS entitlements (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL REFERENCES users(id),
    plan          TEXT NOT NULL,        -- one_time | three_day | seven_day
    starts_on     TEXT NOT NULL,        -- YYYY-MM-DD inclusive
    ends_on       TEXT NOT NULL,        -- YYYY-MM-DD inclusive
    deliveries_used INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'active',
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ent_user ON entitlements(user_id, status);

-- Every job ever shown to a user, so a seven-day plan never repeats itself.
-- The dedupe that JobHunt does globally with its `reported` flag, per-user.
CREATE TABLE IF NOT EXISTS sent_jobs (
    user_id       TEXT NOT NULL,
    fp            TEXT NOT NULL,
    section       TEXT NOT NULL,        -- match | near_miss
    sent_at       TEXT NOT NULL,
    PRIMARY KEY (user_id, fp)
);

-- One digest. Rendered files live on disk; this is the index the dashboard
-- reads, and the record that a paid day was actually delivered.
CREATE TABLE IF NOT EXISTS deliveries (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL REFERENCES users(id),
    entitlement_id TEXT,
    day           TEXT NOT NULL,        -- YYYY-MM-DD
    matches       INTEGER NOT NULL DEFAULT 0,
    near_misses   INTEGER NOT NULL DEFAULT 0,
    html_path     TEXT,
    pdf_path      TEXT,
    email_status  TEXT NOT NULL DEFAULT 'pending',
    summary_json  TEXT,
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_del_user ON deliveries(user_id, day);

-- Free trials run the scorer for anybody with no account, which is an open
-- invitation to be hammered. One row per attempt, keyed by caller, so the
-- route can refuse a fourth run in an hour.
CREATE TABLE IF NOT EXISTS trial_runs (
    id            TEXT PRIMARY KEY,
    caller        TEXT NOT NULL,        -- client IP, or "unknown"
    matches       INTEGER,
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trial_caller ON trial_runs(caller, created_at);

CREATE TABLE IF NOT EXISTS sessions (
    token         TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL REFERENCES users(id),
    created_at    TEXT NOT NULL,
    expires_at    TEXT NOT NULL
);
"""


def connect(path=None):
    conn = sqlite3.connect(path or DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# Columns added after the first databases were already created. CREATE TABLE
# IF NOT EXISTS will not alter a table that already exists, so each one is
# applied by hand, guarded by a check - this file stays the single source of
# truth for the shape and stays safe to run against an existing jobstash.db.
MIGRATIONS = [
    ("users", "google_sub", "ALTER TABLE users ADD COLUMN google_sub TEXT"),
]

# Run after the migrations, because an index cannot be built on a column that
# the ALTER above has not added yet. A SQLite UNIQUE index permits any number
# of NULLs, which is what makes it correct here: every password-only account
# has a NULL google_sub and none of them collide.
POST_MIGRATIONS = [
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub "
    "ON users(google_sub)",
]


def init(path=None):
    # Cloudflare D1 when it is configured and no explicit file was asked for.
    # The schema there is owned by the Worker's migrations (wrangler applies
    # web/migrations/), so this side only opens a connection - it never
    # migrates a database it does not own, and a half-applied ALTER issued
    # from a home connection that dropped mid-flight is exactly the failure
    # that would be unrecoverable.
    if path is None and d1.configured():
        return d1.connect()

    conn = connect(path)
    conn.executescript(SCHEMA)
    for table, column, ddl in MIGRATIONS:
        have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column not in have:
            conn.execute(ddl)
    for ddl in POST_MIGRATIONS:
        conn.execute(ddl)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# passwords - pbkdf2 from the standard library rather than a bcrypt dependency
# ---------------------------------------------------------------------------

# Cloudflare Workers' Web Crypto refuses PBKDF2 above 100,000 iterations
# ("iteration counts above 100000 are not supported"). The web app runs there
# now, so this is a hard ceiling, not a preference - and both sides MUST agree
# or a password set by one cannot be verified by the other. Raising it again
# means leaving Workers.
PBKDF2_ROUNDS = 100_000


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                             salt.encode("utf-8"), PBKDF2_ROUNDS)
    return "pbkdf2$%d$%s$%s" % (PBKDF2_ROUNDS, salt, dk.hex())


def verify_password(password, stored):
    try:
        _, rounds, salt, want = (stored or "").split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 salt.encode("utf-8"), int(rounds))
        return secrets.compare_digest(dk.hex(), want)
    except (ValueError, AttributeError):
        return False


# ---------------------------------------------------------------------------
# small helpers used by both the worker and the web API
# ---------------------------------------------------------------------------

def upsert_job(conn, row, fp):
    """Insert, or just bump last_seen if this job is already known.

    The fingerprint is the primary key, so the same role carried by four boards
    collapses to one row and re-seeing it tomorrow does not create a new one.
    """
    stamp = now_iso()
    cur = conn.execute(
        "UPDATE jobs SET last_seen=?, "
        "description=CASE WHEN length(COALESCE(description,''))"
        " < length(COALESCE(?,'')) THEN ? ELSE description END "
        "WHERE fp=?",
        (stamp, row.get("description"), row.get("description"), fp))
    if cur.rowcount:
        return False                      # already knew about it
    conn.execute(
        "INSERT INTO jobs (fp,source,title,company,location,url,salary,"
        "seniority,posted,description,first_seen,last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (fp, row.get("source"), row.get("title"), row.get("company"),
         row.get("location"), row.get("url"), row.get("salary"),
         row.get("seniority"), row.get("posted"), row.get("description"),
         stamp, stamp))
    return True


def get_profile(conn, user_id):
    r = conn.execute("SELECT profile_json FROM profiles WHERE user_id=?",
                     (user_id,)).fetchone()
    return json.loads(r["profile_json"]) if r else None


def active_entitlement(conn, user_id, day=None):
    day = day or today_iso()
    return conn.execute(
        "SELECT * FROM entitlements WHERE user_id=? AND status='active' "
        "AND starts_on<=? AND ends_on>=? ORDER BY created_at DESC LIMIT 1",
        (user_id, day, day)).fetchone()


def already_sent(conn, user_id):
    return {r["fp"] for r in conn.execute(
        "SELECT fp FROM sent_jobs WHERE user_id=?", (user_id,))}


def mark_sent(conn, user_id, pairs):
    """pairs: iterable of (fp, section)."""
    stamp = now_iso()
    conn.executemany(
        "INSERT OR IGNORE INTO sent_jobs (user_id,fp,section,sent_at) "
        "VALUES (?,?,?,?)",
        [(user_id, fp, section, stamp) for fp, section in pairs])


if __name__ == "__main__":
    c = init()
    tables = [r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    print("initialised", DB_PATH)
    print("tables:", ", ".join(tables))
