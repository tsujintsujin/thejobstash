# -*- coding: utf-8 -*-
"""
The parts that only break when two users run at once.

    python test_concurrency.py

Runs arrive whenever people press Run, so more than one is in flight routinely.
The check here is not about scoring: it is about a run that finds nothing to
score being refunded, never charged for a digest built from nothing.
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import delivery
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


print("\n" + "=" * 68)
print("concurrency checks: %d passed, %d failed" % (passed, failed))
print("=" * 68)
raise SystemExit(1 if failed else 0)
