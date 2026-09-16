# -*- coding: utf-8 -*-
"""
deadRowsDb and freshList - the cleanup round's two side stores.

    freshList.db    what every board lists right now. Wiped and refilled by
                    each round of ingest.py; the pool is compared against it.
    deadRowsDb.db   the record. Every posting the cleanup deleted and why,
                    each board's last good listing size and its flags
                    (blocked, login required), and one summary per round.

Both sit next to jobstash.db (db.DB_PATH), so a test run against a copy of the
pool gets its own copies of these too. Local only, like the pool.
"""
import os, json, sqlite3

import db

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS dead_rows (
    url         TEXT,
    id          TEXT,
    fp          TEXT,
    source      TEXT,
    title       TEXT,
    company     TEXT,
    reason      TEXT NOT NULL,   -- why it was deleted
    http        INTEGER,
    final_url   TEXT,
    deleted_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dead_url    ON dead_rows(url);
CREATE INDEX IF NOT EXISTS idx_dead_source ON dead_rows(source);

-- One row per board. last_count is the listing size of the last round that
-- scraped it cleanly: a round far below it is a failed scrape, not a wave of
-- closed jobs.
CREATE TABLE IF NOT EXISTS boards (
    source          TEXT PRIMARY KEY,
    last_count      INTEGER,
    last_ok_at      TEXT,
    last_error      TEXT,
    skipped_at      TEXT,
    blocked_at      TEXT,           -- the verifier was refused on every page
    login_required  INTEGER NOT NULL DEFAULT 0,
    login_at        TEXT
);

CREATE TABLE IF NOT EXISTS rounds (
    at      TEXT NOT NULL,
    kind    TEXT NOT NULL,          -- scrape | verify
    report  TEXT NOT NULL           -- the JSON the command printed
);
"""

FRESH_SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS fresh (
    source  TEXT NOT NULL,
    url     TEXT,
    fp      TEXT NOT NULL,
    title   TEXT,
    company TEXT
);
CREATE INDEX IF NOT EXISTS idx_fresh_source ON fresh(source);
"""


def _path(name):
    return os.path.join(os.path.dirname(os.path.abspath(db.DB_PATH)), name)


def _open(name, schema):
    conn = sqlite3.connect(_path(name), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.executescript(schema)
    return conn


def connect():
    return _open("deadRowsDb.db", SCHEMA)


def fresh_connect():
    return _open("freshList.db", FRESH_SCHEMA)


def board(conn, source):
    r = conn.execute("SELECT * FROM boards WHERE source=?", (source,)).fetchone()
    return dict(r) if r else {"source": source, "last_count": None,
                              "login_required": 0, "blocked_at": None}


def set_board(conn, source, **cols):
    conn.execute("INSERT OR IGNORE INTO boards (source) VALUES (?)", (source,))
    for k, v in cols.items():
        conn.execute("UPDATE boards SET %s=? WHERE source=?" % k, (v, source))
    conn.commit()


def login_boards(conn):
    return {r["source"] for r in
            conn.execute("SELECT source FROM boards WHERE login_required=1")}


def log_dead(conn, job, reason, http=None, final_url=None):
    conn.execute(
        "INSERT INTO dead_rows (url,id,fp,source,title,company,reason,http,"
        "final_url,deleted_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (job.get("url"), job.get("id"), job.get("fp"), job.get("source"),
         job.get("title"), job.get("company"), reason, http, final_url,
         db.now_iso()))


def log_round(conn, kind, report):
    conn.execute("INSERT INTO rounds (at,kind,report) VALUES (?,?,?)",
                 (db.now_iso(), kind, json.dumps(report)))
    conn.commit()


def report(conn):
    """`python deadrows.py` - what the cleanup has been doing, per board."""
    out = []
    out.append("%-16s %8s  %-20s %-20s %s" % ("board", "listed", "blocked",
                                               "login required", "last error"))
    for b in conn.execute("SELECT * FROM boards ORDER BY source"):
        out.append("%-16s %8s  %-20s %-20s %s" % (
            b["source"], b["last_count"] if b["last_count"] is not None else "-",
            b["blocked_at"] or "-", "yes" if b["login_required"] else "-",
            b["last_error"] or ""))
    out.append("")
    out.append("deleted, by board and reason")
    for r in conn.execute(
            "SELECT source, reason, COUNT(*) n FROM dead_rows "
            "GROUP BY source, reason ORDER BY source, n DESC"):
        out.append("  %-16s %-34s %6d" % (r["source"], r["reason"], r["n"]))
    return "\n".join(out)


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    print(report(connect()))
