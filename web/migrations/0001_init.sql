-- Generated from db.py's SCHEMA. db.py stays the single source of truth for
-- the shape; this file is what wrangler applies to D1.
-- Regenerate with: npm run migration:gen


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

-- Added after the first databases existed. A SQLite UNIQUE index permits any
-- number of NULLs, which is what makes it correct: every password-only
-- account has a NULL google_sub and none of them collide.
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub ON users(google_sub);
