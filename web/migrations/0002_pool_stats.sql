-- The home page's three numbers, written by ingest.py once a day.
--
-- Replaces three aggregates over the whole jobs table on every render. The
-- jobs table itself is no longer needed here: only the scoring machine reads
-- job rows, and it now keeps the pool locally.
CREATE TABLE IF NOT EXISTS pool_stats (
    id            INTEGER PRIMARY KEY,
    pool          INTEGER NOT NULL,
    fresh         INTEGER NOT NULL,
    sources       INTEGER NOT NULL,
    updated_at    TEXT NOT NULL
);

-- Seed from the pool currently in D1 so the page is correct the moment this
-- lands, before the next ingest runs.
INSERT OR REPLACE INTO pool_stats (id, pool, fresh, sources, updated_at)
SELECT 1,
       COUNT(*),
       COALESCE(SUM(CASE WHEN first_seen >= datetime('now','-3 days') THEN 1 ELSE 0 END), 0),
       COUNT(DISTINCT source),
       strftime('%Y-%m-%dT%H:%M:%SZ','now')
FROM jobs;
