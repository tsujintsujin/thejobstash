# -*- coding: utf-8 -*-
"""
JSON CLI the Next.js API routes shell out to.

The web app owns sessions and the database rows it writes itself; anything that
needs the matcher, the resume parser or the renderer comes through here, so
there is exactly one implementation of the scoring rules rather than a
TypeScript reimplementation drifting away from the Python one.

    python api_bridge.py parse   <resume-path> <original-filename>
    python api_bridge.py profile <user_id>
    python api_bridge.py preview <user_id>
    python api_bridge.py deliver <user_id>
    python api_bridge.py stats

Always prints one JSON object on stdout. Errors are JSON too, never a
traceback, so the caller never has to parse a crash.
"""
import os, sys, json, io, traceback

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db, resume_parse as R, delivery, render, mailer, run_delivery
from summarise import summarise


class Out(Exception):
    """The payload a command wants to answer with.

    It used to print and raise SystemExit, which meant the only way to call a
    command was to start a process and read its stdout. `py_server.py` serves
    the same commands over HTTP and would otherwise have had to capture stdout
    and catch SystemExit per request. Unwinding to `run()` instead keeps every
    command body below unchanged and the CLI byte-identical - `__main__` still
    prints exactly one JSON object and exits with the same code.
    """

    def __init__(self, obj, code=0):
        super().__init__(obj.get("error") if isinstance(obj, dict) else "")
        self.obj, self.code = obj, code


def out(obj, code=0):
    raise Out(obj, code)


def cmd_parse(path, filename):
    text = R.extract_text(path, filename)
    if text.startswith("__PARSE_ERROR__"):
        out({"ok": False, "error": "Could not read that file. "
                                   "PDF, DOCX and TXT are supported."}, 0)
    profile, diag = R.parse_profile(text)
    if diag["thin"]:
        # Almost always a scanned PDF with no text layer. Saying so beats
        # silently building a profile out of nothing and matching badly.
        out({"ok": False, "thin": True, "diagnostics": diag,
             "error": "We could only read %d characters from that file. If it "
                      "is a scanned PDF, export a text version and try again."
                      % diag["text_chars"]}, 0)
    out({"ok": True, "profile": R.profile_to_dict(profile),
         "diagnostics": diag, "resume_text": text[:20000]})


def cmd_profile(user_id):
    conn = db.init()
    p = db.get_profile(conn, user_id)
    row = conn.execute("SELECT resume_name,updated_at FROM profiles "
                       "WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    if not p:
        out({"ok": False, "error": "no profile"})
    out({"ok": True, "profile": p,
         "resume_name": row["resume_name"] if row else None,
         "updated_at": row["updated_at"] if row else None})


def _shape(digest):
    """Flatten a digest into something the dashboard can render directly."""
    sec = {}
    for key, rows in digest["sections"].items():
        out_rows = []
        for m in rows:
            d = summarise(m.job.get("description"), m.job.get("salary"))
            out_rows.append({
                "fp": m.job["fp"], "title": m.job["title"],
                "company": m.job["company"], "location": m.job["location"],
                "url": m.job["url"], "source": m.job["source"],
                "score": m.score, "tier": m.tier,
                "reasons": m.reasons[:3],
                "blockers": [{"kind": b.kind, "detail": b.detail}
                             for b in m.blockers],
                # A card with only a title and a score is not enough to decide
                # whether to click, so every one carries what the posting
                # actually says - and a salary line that is never blank.
                "salary": d["salary"], "salary_known": d["salary_known"],
                "summary": d["summary"],
                "responsibilities": d["responsibilities"],
                "requirements": d["requirements"],
            })
        sec[key] = out_rows
    return {"sections": sec, "summary": digest["summary"]}


def cmd_preview(user_id):
    """Score without consuming anything - dry_run keeps sent_jobs untouched."""
    conn = db.init()
    d = delivery.build_digest(conn, user_id, dry_run=True)
    conn.close()
    if "error" in d:
        out({"ok": False, "error": d["error"]})
    out({"ok": True, **_shape(d)})


def cmd_deliver(user_id):
    conn = db.init()
    row = conn.execute("SELECT id,email FROM users WHERE id=?",
                       (user_id,)).fetchone()
    if not row:
        conn.close()
        out({"ok": False, "error": "no such user"})
    res = run_delivery.deliver_one(conn, row["id"], row["email"], dry=False)
    conn.close()
    if "error" in res:
        out({"ok": False, "error": res["error"]})
    out({"ok": True, "result": res})


def cmd_stats():
    conn = db.init()
    jc = db.jobs_conn()
    pool = jc.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
    fresh = jc.execute(
        "SELECT COUNT(*) c FROM jobs WHERE first_seen >= datetime('now','-3 days')"
    ).fetchone()["c"]
    srcs = jc.execute("SELECT COUNT(DISTINCT source) c FROM jobs").fetchone()["c"]
    users = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    conn.close()
    out({"ok": True, "pool": pool, "fresh_3d": fresh, "sources": srcs,
         "users": users})


def run(argv):
    """Dispatch one command. Returns (payload, exit_code), never raises.

    The single entry point for both callers: the CLI below, and the HTTP
    server that exposes the same commands to the Cloudflare Worker.
    """
    try:
        if not argv:
            return {"ok": False, "error": "no command"}, 2
        cmd, rest = argv[0], argv[1:]
        if cmd == "parse":
            cmd_parse(rest[0], rest[1] if len(rest) > 1 else rest[0])
        elif cmd == "profile":
            cmd_profile(rest[0])
        elif cmd == "preview":
            cmd_preview(rest[0])
        elif cmd == "deliver":
            cmd_deliver(rest[0])
        elif cmd == "stats":
            cmd_stats()
        else:
            return {"ok": False, "error": "unknown command " + cmd}, 2
    except Out as o:
        return o.obj, o.code
    except Exception as e:
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, e),
                "trace": traceback.format_exc()[-800:]}, 1
    return {"ok": False, "error": "command produced no output"}, 1


if __name__ == "__main__":
    payload, code = run(sys.argv[1:])
    print(json.dumps(payload, default=str))
    raise SystemExit(code)
