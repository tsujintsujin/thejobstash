-- One row per role family, for the public /jobs pages. Written by ingest.py
-- alongside pool_stats after every cleanup round.
--
-- Aggregates and a dozen example postings per family, never the pool: the
-- job table stays on the scoring machine (see 0002_pool_stats.sql). A family
-- missing from a round's push is deleted, so a page can never outlive its
-- data.
CREATE TABLE IF NOT EXISTS pool_pages (
    slug        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    total       INTEGER NOT NULL,   -- live postings in this family
    fresh       INTEGER NOT NULL,   -- first seen in the last 7 days
    remote      INTEGER NOT NULL,   -- of total, remote or work-from-home
    with_pay    INTEGER NOT NULL,   -- of total, the posting states pay
    examples    TEXT NOT NULL,      -- JSON [{title, company, location, salary, posted}]
    updated_at  TEXT NOT NULL
);
