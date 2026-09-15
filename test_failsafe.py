# -*- coding: utf-8 -*-
"""
The failsafe: a run the pipeline could not finish gets closed, and its credit
handed back, exactly once.

This is what stands between a paying customer and a progress bar that spins for
45 minutes after a failure that took three seconds. Runs against a temporary
sqlite file - never D1, never jobstash.db.

    python test_failsafe.py
"""
import os, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["JOBSTASH_USE_D1"] = "0"

import db, run_delivery

fails = []
ran = []


def check(name, got, want):
    ok = got == want
    ran.append(name)
    print("  %-52s %s" % (name, "ok" if ok else "FAIL  got %r want %r" % (got, want)))
    if not ok:
        fails.append(name)


def credits(conn, uid):
    return conn.execute("SELECT credits FROM users WHERE id=?", (uid,)).fetchone()["credits"]


def status(conn, run):
    return conn.execute("SELECT status FROM runs WHERE id=?", (run,)).fetchone()["status"]


def seed(conn, uid, run, state="queued"):
    conn.execute("INSERT INTO users (id,email,credits,created_at) VALUES (?,?,?,?)",
                 (uid, uid + "@test.invalid", 0, db.now_iso()))
    conn.execute("INSERT INTO runs (id,user_id,status,created_at,updated_at) "
                 "VALUES (?,?,?,?,?)", (run, uid, state, db.now_iso(), db.now_iso()))
    conn.commit()


def main():
    tmp = os.path.join(tempfile.mkdtemp(), "failsafe.db")
    conn = db.init(tmp)
    print("failsafe checks")
    print("-" * 68)

    # The case that started this: the scorer could not look the user up, so it
    # never knew whose run it was. The run id alone has to be enough.
    seed(conn, "usr_a", "run_a")
    check("closes a queued run without knowing the user",
          run_delivery.fail_run(conn, "run_a", None, "boom"), True)
    check("  status is failed", status(conn, "run_a"), "failed")
    check("  credit returned", credits(conn, "usr_a"), 1)

    # Called twice - the workflow's failsafe fires after run_delivery.py may
    # already have closed the run itself. The second must be a no-op, or a
    # failed run pays out twice.
    check("second call closes nothing",
          run_delivery.fail_run(conn, "run_a", None, "boom"), False)
    check("  credit not returned twice", credits(conn, "usr_a"), 1)

    # A run already in flight still gets closed: it died mid-run, and the user
    # is watching a bar that will never move.
    seed(conn, "usr_b", "run_b", "running")
    check("closes a running run", run_delivery.fail_run(conn, "run_b", None, "boom"), True)
    check("  credit returned", credits(conn, "usr_b"), 1)

    # A finished run is untouchable: closing it would refund a delivered digest.
    seed(conn, "usr_c", "run_c", "done")
    check("leaves a finished run alone",
          run_delivery.fail_run(conn, "run_c", None, "boom"), False)
    check("  no credit returned", credits(conn, "usr_c"), 0)

    # With a user id given, it must match - the guard the digest path relies on.
    seed(conn, "usr_d", "run_d")
    check("refuses another user's run",
          run_delivery.fail_run(conn, "run_d", "usr_a", "boom"), False)
    check("  credit stays put", credits(conn, "usr_d"), 0)
    check("accepts the right user", run_delivery.fail_run(conn, "run_d", "usr_d", "boom"), True)

    conn.close()
    print("-" * 68)
    print("%d passed, %d failed" % (len(ran) - len(fails), len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
