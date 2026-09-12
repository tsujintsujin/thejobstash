# -*- coding: utf-8 -*-
"""
The daily delivery run. This is what the n8n workflow calls.

    python run_delivery.py --json           every eligible user
    python run_delivery.py --user <id>      one user, ignores entitlement
    python run_delivery.py --dry            score and render, send nothing,
                                            and do not consume any jobs

Writes its human log to stderr and a JSON document to stdout, matching the
convention JobHunt's sweep already uses so the n8n Code nodes parse the same
way.

A thin day extends the plan by a day rather than consuming it. That single rule
is what stops a quiet week turning into a refund.
"""
import os, sys, json, io, argparse, traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import db, delivery, render, mailer, r2


def log(msg):
    print(msg, file=sys.stderr)


def deliver_one(conn, user_id, email, entitlement=None, dry=False):
    digest = delivery.build_digest(conn, user_id, dry_run=dry)
    if "error" in digest:
        return {"user_id": user_id, "email": email, "error": digest["error"]}

    s = digest["summary"]
    html_path, pdf_path = render.write_digest(digest, user_id, email)

    status, detail = "skipped", "dry run"
    if not dry:
        with open(html_path, encoding="utf-8") as fh:
            body = fh.read()
        status, detail = mailer.send(email, mailer.subject_for(s), body, pdf_path)

    # A day that could not be filled is not a day the user should pay for.
    extended = False
    if s["thin"] and entitlement and not dry:
        delivery.extend_entitlement(conn, entitlement["id"])
        extended = True

    # The Worker serving the dashboard has no disk and no route back to this
    # machine, so the rendered pair goes up to R2 and the row records the key
    # instead of a path that only exists here. Best-effort: a failed upload
    # leaves the local path and costs a download button, not a delivery.
    stored_html, stored_pdf = html_path, pdf_path
    if not dry and r2.configured():
        stored_html, stored_pdf = r2.put_digest(user_id, s["day"],
                                                html_path, pdf_path)

    if not dry:
        conn.execute(
            "INSERT INTO deliveries (id,user_id,entitlement_id,day,matches,"
            "near_misses,html_path,pdf_path,email_status,summary_json,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (db.new_id("dlv_"), user_id,
             entitlement["id"] if entitlement else None, s["day"],
             s["matches"], s["near_misses"], stored_html, stored_pdf, status,
             json.dumps(s), db.now_iso()))
        if entitlement:
            conn.execute(
                "UPDATE entitlements SET deliveries_used=deliveries_used+1 "
                "WHERE id=?", (entitlement["id"],))
        conn.commit()

    return {"user_id": user_id, "email": email, "matches": s["matches"],
            "near_misses": s["near_misses"], "thin": s["thin"],
            "backfilled": s["backfilled"], "reserve_left": s["reserve_left"],
            "first_ever": s["first_ever"], "plan_extended": extended,
            "html": html_path, "pdf": pdf_path,
            "email_status": status, "email_detail": detail}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--user")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    conn = db.init()
    results, failures = [], []

    if args.user:
        row = conn.execute("SELECT id,email FROM users WHERE id=? OR email=?",
                           (args.user, args.user)).fetchone()
        if not row:
            log("no such user: %s" % args.user)
            print(json.dumps({"error": "no such user", "delivered": 0}))
            return 2
        targets = [{"user_id": row["id"], "email": row["email"], "ent": None}]
    else:
        targets = [{"user_id": e["user_id"], "email": e["email"], "ent": e}
                   for e in delivery.eligible_users(conn)]

    log("delivering to %d user(s)%s" % (len(targets), " [dry]" if args.dry else ""))
    for t in targets:
        try:
            r = deliver_one(conn, t["user_id"], t["email"], t["ent"], args.dry)
            results.append(r)
            if "error" in r:
                log("  %-28s ERROR %s" % (t["email"], r["error"]))
                failures.append(r)
            else:
                log("  %-28s %2d matches, %2d close%s  [%s]"
                    % (t["email"], r["matches"], r["near_misses"],
                       "  THIN, +1 day" if r["thin"] else "", r["email_status"]))
        except Exception as e:
            log("  %-28s CRASH %s" % (t["email"], e))
            log(traceback.format_exc())
            failures.append({"user_id": t["user_id"], "email": t["email"],
                             "error": "%s: %s" % (type(e).__name__, e)})

    pool = conn.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
    conn.close()

    doc = {"day": db.today_iso(), "delivered": len([r for r in results
                                                    if "error" not in r]),
           "failed": len(failures), "pool": pool, "results": results,
           "failures": failures, "dry_run": args.dry}
    if args.json:
        print(json.dumps(doc, indent=2))
    else:
        print(json.dumps({k: doc[k] for k in
                          ("day", "delivered", "failed", "pool")}))
    return 1 if failures and not results else 0


if __name__ == "__main__":
    raise SystemExit(main())
