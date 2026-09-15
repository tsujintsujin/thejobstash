# -*- coding: utf-8 -*-
"""
A sqlite3-shaped connection backed by Cloudflare D1's HTTP API.

Why a shim rather than a rewrite: every query in this project is already
written against `sqlite3` - `conn.execute(sql, params).fetchone()`, rows
indexed by column name, `executemany`, `commit`. D1 *is* SQLite, so the SQL
itself needs no change at all. Matching what `sqlite3` already exposes means
`matching.py`, `delivery.py` and `run_delivery.py` move to D1 without a single
line being touched, which is the only version of this migration where the
scoring rules cannot quietly drift.

Used when the site has moved to Cloudflare: D1 is then the one source of truth
and this machine reaches it over HTTPS like any other client. Without the env
vars, `db.init()` still opens the local file, so the tests and Justin's own
JobHunt tooling keep working unchanged.

Queries go through the site's own /api/internal/d1 rather than Cloudflare's
D1 REST API. That endpoint holds the database as a Worker binding, so this
machine needs no Cloudflare API token at all - just the shared secret it
already has for the tunnel. An account-scoped API token sitting on a home PC
would reach every database in the account; this reaches exactly one.

Env:
  JOBSTASH_SITE_ORIGIN  https://thejobstash.com
  JOBSTASH_PY_TOKEN     the shared secret, same one py_server.py uses
"""
import os, json, time, urllib.request, urllib.error

UA = "TheJobStash-scorer/1.0 (+https://thejobstash.com)"


class D1Error(RuntimeError):
    pass


class Row(dict):
    """D1 returns JSON objects; sqlite3.Row is indexed the same way.

    Subclassing dict means `r["col"]` and `dict(r)` - the only two things the
    callers ever do with a row - both work with no adapter.
    """
    __slots__ = ()


class Cursor:
    """The parts of sqlite3.Cursor this codebase actually uses."""

    def __init__(self, rows, changes):
        self._rows = rows
        self.rowcount = changes
        self.lastrowid = None

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def __iter__(self):
        return iter(self._rows)


class Connection:
    """Speaks sqlite3's interface, executes against D1 over HTTPS.

    There is no transaction to manage: every D1 request commits on its own, so
    `commit()` is a no-op kept only so callers do not have to care which
    backend they hold. That is a real behaviour difference from the local file:
    a crash mid-run leaves whatever was already written, not a rolled-back
    transaction.
    """

    def __init__(self, origin, token, timeout=60):
        self._url = origin.rstrip("/") + "/api/internal/d1"
        self._token = token
        self._timeout = timeout

    # -- transport ---------------------------------------------------------
    def _post(self, body):
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self._url,
            data=data,
            headers={
                "Authorization": "Bearer " + self._token,
                "Content-Type": "application/json",
                # Cloudflare's bot rules answer 403 (error 1010) to
                # "Python-urllib/3.x" before the request ever reaches the
                # Worker. Identifying honestly as this project's own client
                # is what gets through, not pretending to be a browser.
                "User-Agent": UA,
            },
            method="POST",
        )
        # D1 occasionally answers 5xx under contention. Three tries with a
        # short backoff turns a transient blip into a slow query instead of a
        # failed delivery; anything past that is a real outage and should say
        # so rather than retry forever.
        last = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:400]
                if e.code < 500:
                    raise D1Error("D1 %d: %s" % (e.code, detail))
                last = D1Error("D1 %d: %s" % (e.code, detail))
            except urllib.error.URLError as e:
                last = D1Error("D1 unreachable: %s" % e)
            time.sleep(0.4 * (attempt + 1))
        raise last

    def _query(self, sql, params=()):
        payload = self._post({"sql": sql, "params": [_bind(p) for p in params]})
        if not payload.get("success"):
            raise D1Error("D1 refused: %s" % json.dumps(payload.get("errors"))[:400])
        res = payload["result"][0]
        rows = [Row(r) for r in (res.get("results") or [])]
        meta = res.get("meta") or {}
        return Cursor(rows, meta.get("changes", 0) or 0)

    # -- sqlite3 surface ---------------------------------------------------
    def execute(self, sql, params=()):
        return self._query(sql, params)

    def executemany(self, sql, seq):
        seq = list(seq)
        if not seq:
            return Cursor([], 0)
        # One request carrying every statement, not one request per row.
        # Thirty rows as thirty round-trips to Cloudflare from a home
        # connection is seconds of wall clock.
        changes = 0
        for chunk in _chunks(seq, 50):
            body = [{"sql": sql, "params": [_bind(p) for p in row]} for row in chunk]
            payload = self._post(body)
            if not payload.get("success"):
                raise D1Error("D1 refused: %s" % json.dumps(payload.get("errors"))[:400])
            for res in payload["result"]:
                changes += (res.get("meta") or {}).get("changes", 0) or 0
        return Cursor([], changes)

    def executescript(self, script):
        for stmt in _split(script):
            self._query(stmt)
        return Cursor([], 0)

    def commit(self):
        """No-op: each D1 request is its own transaction."""

    def rollback(self):
        """No-op, for the same reason. Nothing is held open to undo."""

    def close(self):
        """No-op: there is no socket to keep, each query is a fresh request."""


def _bind(v):
    """D1 accepts JSON scalars only."""
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, (int, float, str)) or v is None:
        return v
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    return str(v)


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _split(script):
    """Split a schema script on semicolons that end a statement.

    Deliberately simple - it only ever runs over this project's own SCHEMA
    constant, which has no semicolons inside string literals. It is not a SQL
    parser and must not be pointed at arbitrary input.
    """
    out, buf = [], []
    for line in script.splitlines():
        s = line.strip()
        if not s or s.startswith("--"):
            continue
        buf.append(line)
        if s.endswith(";"):
            stmt = "\n".join(buf).strip().rstrip(";").strip()
            if stmt:
                out.append(stmt)
            buf = []
    tail = "\n".join(buf).strip()
    if tail:
        out.append(tail)
    return out


def configured():
    return bool(
        os.environ.get("JOBSTASH_SITE_ORIGIN")
        and os.environ.get("JOBSTASH_PY_TOKEN")
        and os.environ.get("JOBSTASH_USE_D1", "1") != "0"
    )


def connect():
    return Connection(
        os.environ["JOBSTASH_SITE_ORIGIN"],
        os.environ["JOBSTASH_PY_TOKEN"],
    )
