# -*- coding: utf-8 -*-
"""
Delete jobs no board has listed for 30 days.

Its own n8n workflow (n8n/workflows/jobstash-prune.json), not a step of the
daily run, so the main workflow stays about ingest and delivery.

last_seen, not first_seen: ingest bumps last_seen every time a board still
lists the job. Deleting on first_seen would drop a job that is still open,
and the next ingest would re-insert it as brand new.

    python prune_jobs.py            human log
    python prune_jobs.py --json     one JSON document on stdout, for n8n
"""
import io, json, os, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db

RETENTION_DAYS = 30


def prune(conn, days=RETENTION_DAYS):
    cur = conn.execute("DELETE FROM jobs WHERE last_seen < datetime('now', ?)",
                       ("-%d days" % days,))
    conn.commit()
    return cur.rowcount


if __name__ == "__main__":
    conn = db.jobs_conn()
    out = {"pruned": prune(conn), "days": RETENTION_DAYS,
           "pool": conn.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]}
    conn.close()
    if "--json" in sys.argv:
        print(json.dumps(out))
    else:
        print("pruned %(pruned)d jobs unseen for %(days)d days, pool now %(pool)d" % out)
