# -*- coding: utf-8 -*-
"""
One run of one resume. n8n's run workflow calls this when a user presses Run
on the dashboard; nothing calls it on a schedule.

    python run_delivery.py --json --user <id> --run <run_id>
    python run_delivery.py --user <id|email> --dry     score and render, send
                                                       nothing, consume nothing

A run costs one credit. The site takes it when it creates the runs row, before
this starts. This marks that row done - or failed, and a failed run hands the
credit straight back, so a crash never costs anyone a paid run.

Writes its human log to stderr and one JSON document to stdout, matching the
convention JobHunt's sweep already uses so the n8n Code nodes parse the same
way.
"""
import os, sys, json, io, argparse, traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import db, delivery, render, mailer, r2

OPEN = "('queued','running')"
FAILED_COPY = "The run failed on our side. Your credit has been returned."


def log(msg):
    print(msg, file=sys.stderr)


def deliver_one(conn, user_id, email, dry=False):
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

    # The Worker serving the dashboard has no disk and no route back to this
    # machine, so the rendered pair goes up to R2 and the row records the key
    # instead of a path that only exists here. Best-effort: a failed upload
    # leaves the local path and costs a download button, not a delivery.
    stored_html, stored_pdf = html_path, pdf_path
    if not dry and r2.configured():
        stored_html, stored_pdf = r2.put_digest(user_id, s["day"],
                                                html_path, pdf_path)

    # The id is minted before the insert because the caller needs it: the
    # dashboard's "view your stash" link is /api/download/<id>, the same route
    # the Past digests row uses, so there is one way to open a digest.
    dlv_id = db.new_id("dlv_")
    if not dry:
        conn.execute(
            "INSERT INTO deliveries (id,user_id,day,matches,near_misses,"
            "html_path,pdf_path,email_status,summary_json,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (dlv_id, user_id, s["day"], s["matches"], s["near_misses"],
             stored_html, stored_pdf, status, json.dumps(s), db.now_iso()))
        conn.commit()

    return {"user_id": user_id, "email": email,
            "delivery_id": None if dry else dlv_id,
            "matches": s["matches"],
            "near_misses": s["near_misses"], "thin": s["thin"],
            "backfilled": s["backfilled"], "reserve_left": s["reserve_left"],
            "first_ever": s["first_ever"],
            "html": html_path, "pdf": pdf_path,
            "email_status": status, "email_detail": detail}


def mark_run(conn, run_id, user_id, status, delivery_id=None):
    conn.execute(
        "UPDATE runs SET status=?, delivery_id=?, updated_at=? "
        "WHERE id=? AND user_id=? AND status IN " + OPEN,
        (status, delivery_id, db.now_iso(), run_id, user_id))
    conn.commit()


def fail_run(conn, run_id, user_id, error):
    """Close the run as failed and return its credit - once.

    The status flip goes first and only succeeds while the run is still open,
    so the refund can only follow one flip. The site's stale-run sweep closes
    runs under the same guard; whichever closes the run is the one that
    refunds.
    """
    rows = conn.execute(
        "UPDATE runs SET status='failed', error=?, updated_at=? "
        "WHERE id=? AND user_id=? AND status IN " + OPEN + " RETURNING id",
        (error[:500], db.now_iso(), run_id, user_id)).fetchall()
    if rows:
        conn.execute("UPDATE users SET credits=credits+1 WHERE id=?", (user_id,))
    conn.commit()
    return bool(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--user", required=True)
    ap.add_argument("--run")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    # Started by n8n, so it inherits no environment - see db.use_live_store().
    db.use_live_store()
    conn = db.init()

    row = conn.execute("SELECT id,email FROM users WHERE id=? OR email=?",
                       (args.user, args.user)).fetchone()
    claimed = False
    if not row:
        r = {"user_id": args.user, "error": "no such user"}
    else:
        claimed = True
        if args.run:
            # The site creates the row, and takes the credit, before n8n is
            # ever called. A run id with no queued row behind it for this user
            # did not come from the site - someone reached the webhook some
            # other way - so it gets nothing rather than a free digest.
            claimed = conn.execute(
                "UPDATE runs SET status='running', updated_at=? "
                "WHERE id=? AND user_id=? AND status='queued'",
                (db.now_iso(), args.run, row["id"])).rowcount == 1
            conn.commit()
        if not claimed:
            r = {"user_id": row["id"], "email": row["email"],
                 "error": "run not found for this user, or already handled"}
        else:
            try:
                r = deliver_one(conn, row["id"], row["email"], args.dry)
            except Exception as e:
                log(traceback.format_exc())
                r = {"user_id": row["id"], "email": row["email"],
                     "error": "%s: %s" % (type(e).__name__, e)}

    if args.run and row and claimed:
        if "error" in r:
            # The detail stays in this document for the ops report; the user
            # is told plainly, without a stack trace's worth of internals.
            r["credit_returned"] = fail_run(conn, args.run, row["id"],
                                            FAILED_COPY)
        else:
            mark_run(conn, args.run, row["id"], "done", r["delivery_id"])

    pool = db.jobs_conn().execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
    conn.close()

    ok = "error" not in r
    if ok:
        log("  %-28s %2d matches, %2d close  [%s]"
            % (r["email"], r["matches"], r["near_misses"], r["email_status"]))
    else:
        log("  %-28s ERROR %s" % (r.get("email") or args.user, r["error"]))

    doc = {"day": db.today_iso(), "run_id": args.run, "ok": ok, "result": r,
           "pool": pool, "dry_run": args.dry}
    if args.json:
        print(json.dumps(doc, indent=2))
    else:
        print(json.dumps({k: doc[k] for k in ("day", "run_id", "ok", "pool")}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
