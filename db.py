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

The core tables:

  jobs          the shared pool, scraped once, read by every user
  profiles      one per user - the thing JobHunt/profile.py hard-codes
  payments      PayMongo credit-pack checkouts (credits live on users)
  runs          one per credit spent; deliveries is what each run produced

Nothing records which jobs a user has been shown. Every run scores the whole
pool fresh; there is no per-day or per-user history to filter against.
"""
import os, sqlite3, json, hashlib, secrets, datetime, io, re, sys

import d1

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("JOBSTASH_DB", os.path.join(HERE, "jobstash.db"))


def load_env(path=None):
    """Put .env.cloudflare into os.environ, unless the caller already set it.

    Explicit environment wins, so JOBSTASH_USE_D1=0 and the tests still work.
    """
    path = path or os.path.join(HERE, ".env.cloudflare")
    if not os.path.exists(path):
        return False
    with io.open(path, encoding="utf-8") as fh:
        for k, v in re.findall(r"^([A-Z0-9_]+)=(.*)$", fh.read(), re.M):
            if v and k not in os.environ:
                os.environ[k] = v.strip()
    return True


def jobs_conn(path=None):
    """The shared job pool. ALWAYS local, never D1.

    The pool is read in full by matching.py and written in full by ingest.py,
    and nothing else reads a job row - the site only ever wanted three counts
    from it (see pool_stats above). Keeping it in D1 meant this machine pulled
    a few megabytes back down through the Worker to score one resume, which is
    both the slow part of every scan and what exhausted the Worker's CPU
    budget on 2026-09-12. Jobs belong next to the Python that uses them.

    Accounts - users, sessions, profiles, credits, deliveries - stay in
    D1 via init(), because the site genuinely needs them.
    """
    return init(path or DB_PATH)


def use_live_store():
    """Called by the entry points that must reach the deployed pool.

    d1.configured() reads os.environ, and nothing was putting .env.cloudflare
    there for a process the *scheduler* started. An n8n executeCommand node
    runs a bare `python ingest.py --json`, inheriting none of it, so
    d1.configured() was False and init() opened the local sqlite file. Nothing
    raised: the scrape succeeded, the workflow reported success, and the live
    pool never moved - a full nightly scrape written into a database the site
    does not read.

    Deliberately NOT inside init(): D1 must stay opt-in, or JobHunt tooling and
    every test would start needing a network and a token. This is the opt-in.
    """
    had_env = load_env()
    if d1.configured():
        return True
    if had_env and os.environ.get("JOBSTASH_USE_D1", "1") != "0":
        sys.stderr.write(
            "[db] WARNING: .env.cloudflare is present but D1 is not "
            "configured - writing to %s, which the live site does not "
            "read.\n" % DB_PATH)
    return False


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


# The date a user sees on their digest, in their own day - not UTC's.
# Everything else here is UTC on purpose (now_iso, the SQL `datetime('now')`),
# but `day` is the label on a Stash row and the name of a downloaded PDF, and
# PH is UTC+8: a run at 7am Manila is still yesterday in UTC, so every run
# between midnight and 8am was stamped with the wrong day. Fixed offset rather
# than zoneinfo because the Philippines has had no DST since 1978 and tzdata
# is not installed on the scorer machine.
MANILA = datetime.timezone(datetime.timedelta(hours=8))


def today_iso():
    return datetime.datetime.now(MANILA).strftime("%Y-%m-%d")


def new_id(prefix=""):
    return prefix + secrets.token_hex(8)


SCHEMA = """
PRAGMA journal_mode=WAL;

-- The shared pool. Scraped once and shared, regardless of how many users exist;
-- this is what makes the marginal cost of user 500 the same as user 1.
CREATE TABLE IF NOT EXISTS jobs (
    -- One row per board posting: the same role on four boards is four rows,
    -- each with its own link and its own status. Collapsing them is the
    -- result's job (delivery.py), not the pool's - a merged row kept only the
    -- first board's link, so when that board dropped it the row kept a dead
    -- link while another board still had the job open.
    id            TEXT PRIMARY KEY,     -- posting_id(): board + link
    fp            TEXT NOT NULL,        -- normalised company+title; groups one job across boards
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
    -- valid | unverified | login_required. Set by the cleanup round
    -- (ingest.py) and the verifier (verify.py). Only valid and
    -- login_required are scored; a dead posting is deleted, not kept.
    status        TEXT NOT NULL DEFAULT 'valid',
    -- When verify.py last found the page alive. A board whose scraper reads
    -- only part of its listing leaves most of its live jobs "missing" every
    -- round; this stops them being re-checked every three hours.
    checked_at    TEXT,
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
    -- One run of a resume each. The default is the free credit every account
    -- starts with, so no signup path has to grant it.
    credits       INTEGER NOT NULL DEFAULT 1,
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

-- One PayMongo checkout. Credits are added only when PayMongo's own record of
-- the intent says paid; the pending -> paid flip makes that count once.
CREATE TABLE IF NOT EXISTS payments (
    id            TEXT PRIMARY KEY,     -- pay_<hex>, our reference
    user_id       TEXT NOT NULL REFERENCES users(id),
    pack          TEXT NOT NULL,        -- id from web/lib/packs.ts
    credits       INTEGER NOT NULL,
    amount        INTEGER NOT NULL,     -- centavos actually charged
    checkout_id   TEXT UNIQUE,          -- PayMongo payment intent, pi_...
    status        TEXT NOT NULL DEFAULT 'pending',  -- pending | paid
    created_at    TEXT NOT NULL,
    paid_at       TEXT
);
CREATE INDEX IF NOT EXISTS idx_pay_user ON payments(user_id, created_at);

-- One run of one resume. The credit is taken when the row is created and
-- handed back if the run fails.
CREATE TABLE IF NOT EXISTS runs (
    id            TEXT PRIMARY KEY,     -- run_<hex>
    user_id       TEXT NOT NULL REFERENCES users(id),
    status        TEXT NOT NULL DEFAULT 'queued',   -- queued | running | done | failed
    delivery_id   TEXT,
    error         TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_user ON runs(user_id, created_at);

-- One digest. Rendered files live on disk; this is the index the dashboard
-- reads, and the record that a paid run was actually delivered.
CREATE TABLE IF NOT EXISTS deliveries (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL REFERENCES users(id),
    day           TEXT NOT NULL,        -- YYYY-MM-DD, a display label only
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

-- Password sign-up emails a code before any account exists; a correct code
-- creates the account from this row and deletes it. Only a hash of the code
-- is stored, and attempts caps the guesses one code can take. (web migration 0004)
CREATE TABLE IF NOT EXISTS signup_codes (
    email         TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    code_hash     TEXT NOT NULL,
    attempts      INTEGER NOT NULL DEFAULT 0,
    expires_at    TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

-- Three numbers the home page shows, written by ingest.py after every sweep.
-- The page used to compute these with three aggregates over every row in
-- jobs, on every render. That is the most expensive thing on the busiest
-- page, and it is why the pool had to live on Cloudflare at all - the site
-- wanted counts, so the whole table went up. One row of counts costs nothing
-- and lets the pool live where the Python that reads it lives.
CREATE TABLE IF NOT EXISTS pool_stats (
    id            INTEGER PRIMARY KEY,      -- always 1
    pool          INTEGER NOT NULL,
    fresh         INTEGER NOT NULL,
    sources       INTEGER NOT NULL,
    updated_at    TEXT NOT NULL
);
"""


def posting_id(source, url, fp):
    """The pool's key: one board's one posting. A posting with no link falls
    back to its fingerprint so two linkless rows on one board still differ."""
    return hashlib.sha1(("%s|%s" % (source, url or ("fp:" + fp))
                         ).encode("utf-8")).hexdigest()


def _rebuild_jobs(conn):
    """Move a pool keyed on company+title to one row per posting.

    ALTER TABLE cannot change a primary key, so the table is rebuilt. Every
    existing row carries on as valid; the next cleanup round decides.
    """
    have = {r["name"] for r in conn.execute("PRAGMA table_info(jobs)")}
    if not have or "id" in have:
        return
    conn.create_function("posting_id", 3, posting_id)
    conn.executescript("""
        ALTER TABLE jobs RENAME TO jobs_by_fp;
        DROP INDEX IF EXISTS idx_jobs_first_seen;
        DROP INDEX IF EXISTS idx_jobs_source;
    """)
    conn.executescript(SCHEMA.split("CREATE TABLE IF NOT EXISTS users")[0])
    conn.execute(
        "INSERT OR IGNORE INTO jobs (id,fp,source,title,company,location,url,"
        "salary,seniority,posted,description,status,first_seen,last_seen) "
        "SELECT posting_id(source,url,fp),fp,source,title,company,location,url,"
        "salary,seniority,posted,description,'valid',first_seen,last_seen "
        "FROM jobs_by_fp")
    conn.execute("DROP TABLE jobs_by_fp")
    conn.commit()


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
    "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_url    ON jobs(url)",
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
    # D1 stays opt-in: init() never loads .env.cloudflare itself. Production
    # entry points call use_live_store() first; tests and JobHunt tooling get
    # the local file without needing a network or a token.
    # test_cloudflare.py asserts this and is right to.
    if path is None and d1.configured():
        return d1.connect()

    conn = connect(path)
    _rebuild_jobs(conn)
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

def upsert_job(conn, row, fp, status="valid"):
    """Insert a posting, or mark a known one as listed again.

    Keyed on the posting (board + link), not the job: the same role on another
    board is another row. Seeing it listed makes it `status` again, whatever a
    previous round said.
    """
    stamp = now_iso()
    pid = posting_id(row.get("source"), row.get("url"), fp)
    cur = conn.execute(
        "UPDATE jobs SET last_seen=?, status=?, "
        "description=CASE WHEN length(COALESCE(description,''))"
        " < length(COALESCE(?,'')) THEN ? ELSE description END "
        "WHERE id=?",
        (stamp, status, row.get("description"), row.get("description"), pid))
    if cur.rowcount:
        return False                      # already knew about it
    conn.execute(
        "INSERT INTO jobs (id,fp,source,title,company,location,url,salary,"
        "seniority,posted,description,status,first_seen,last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (pid, fp, row.get("source"), row.get("title"), row.get("company"),
         row.get("location"), row.get("url"), row.get("salary"),
         row.get("seniority"), row.get("posted"), row.get("description"),
         status, stamp, stamp))
    return True


def get_profile(conn, user_id):
    r = conn.execute("SELECT profile_json FROM profiles WHERE user_id=?",
                     (user_id,)).fetchone()
    return json.loads(r["profile_json"]) if r else None


if __name__ == "__main__":
    c = init()
    tables = [r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    print("initialised", DB_PATH)
    print("tables:", ", ".join(tables))
