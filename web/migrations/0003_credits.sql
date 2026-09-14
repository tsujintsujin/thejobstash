-- Credits replace time-boxed plans (2026-09-14). One credit is one run of a
-- resume: scrape, score, digest. There is no daily delivery any more, so the
-- entitlement window that governed it is gone with it.

-- Every account, new or existing, starts with one free credit. The default is
-- the grant: signup and Google sign-in need no code to hand it out.
ALTER TABLE users ADD COLUMN credits INTEGER NOT NULL DEFAULT 1;

-- One PayMongo checkout. Credits are added only when PayMongo's own record of
-- the intent says paid, and the pending -> paid flip is what makes a webhook
-- and the buy modal's polling arriving together count once.
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
-- handed back if the run fails; a scrape takes longer than Cloudflare holds a
-- request open, so the dashboard polls this row instead of waiting.
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

DROP TABLE IF EXISTS entitlements;
ALTER TABLE deliveries DROP COLUMN entitlement_id;
