# -*- coding: utf-8 -*-
"""
The parts that only break when two users run at once.

    python test_concurrency.py

Runs arrive whenever people press Run, so more than one is in flight routinely.
Neither of the checks here is about scoring; both are about a run that raced
another one still ending up either correct or refunded, never charged for a
digest built from nothing.
"""
import os, sys, time, threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ingest, delivery
from resume_parse import Profile

passed = failed = 0


def check(label, got, want):
    global passed, failed
    if got == want:
        passed += 1
        print("  ok    %s" % label)
    else:
        failed += 1
        print("  FAIL  %s\n          got  %r\n          want %r" % (label, got, want))


# -- an empty pool is a failure, not a 0-match digest ------------------------
#
# The pool going empty - a fresh install, every board failing, or a run that
# arrived while the sweep meant to fill it was still going - used to produce a
# digest with no jobs in it. run_delivery.py marked that run done and kept the
# credit. It has to come back as an error so the run fails and refunds.
_real = (delivery.db.get_profile, delivery.db.jobs_conn, delivery._rows_for,
         delivery.profile_from_dict)
try:
    delivery.db.get_profile = lambda conn, uid: {"stub": True}
    delivery.db.jobs_conn = lambda: None
    delivery.profile_from_dict = lambda d: Profile()

    delivery._rows_for = lambda conn, since=None: []
    empty = delivery.build_digest(None, "usr_0000000000000000")
    check("empty pool returns an error", "error" in empty, True)

    # Same guard must not fire on a pool that has jobs - a 0-match digest from
    # a real pool is a product outcome, not a broken pipeline, and the user
    # still gets their near-misses.
    delivery._rows_for = lambda conn, since=None: [{"fp": "x"}]
    delivery.M.score_many = lambda rows, profile: []
    full = delivery.build_digest(None, "usr_0000000000000000")
    check("pool with jobs still builds a digest", "error" in full, False)
    check("  and that digest is honestly empty", full["summary"]["matches"], 0)
finally:
    (delivery.db.get_profile, delivery.db.jobs_conn, delivery._rows_for,
     delivery.profile_from_dict) = _real


# -- --wait actually waits for the sweep in flight ---------------------------
lock_held = os.path.exists(ingest.LOCK)
if lock_held:
    print("\n  skipped the lock checks - a real sweep is running right now")
else:
    ingest.POLL_S = 0.05
    open(ingest.LOCK, "w").close()
    try:
        # Someone else's sweep finishes while we wait.
        threading.Timer(0.3, lambda: os.path.exists(ingest.LOCK)
                        and os.unlink(ingest.LOCK)).start()
        t0 = time.time()
        check("waits for a sweep, then returns", ingest.wait_for_lock(), True)
        check("  and it actually waited", time.time() - t0 > 0.2, True)
        check("  and did not leave the lock behind", os.path.exists(ingest.LOCK), False)

        # A lock nobody is going to release must not hang a run forever.
        open(ingest.LOCK, "w").close()
        ingest.LOCK_STALE_S = 0
        check("gives up past the stale deadline", ingest.wait_for_lock(), False)
    finally:
        ingest.LOCK_STALE_S = 60 * 60
        ingest.POLL_S = 15
        if os.path.exists(ingest.LOCK):
            os.unlink(ingest.LOCK)

print("\n" + "=" * 68)
print("concurrency checks: %d passed, %d failed" % (passed, failed))
print("=" * 68)
raise SystemExit(1 if failed else 0)
