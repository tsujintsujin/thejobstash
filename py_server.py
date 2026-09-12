# -*- coding: utf-8 -*-
"""
The scorer, over HTTP, for the Cloudflare Worker to call.

Cloudflare Workers cannot start a process, so the `spawn()` that `lib/py.ts`
used to do became a `fetch()`. This serves the exact same commands
`api_bridge.py` has always served, with the same JSON contract, so nothing
downstream of the bridge changed - `matching.py`, `resume_parse.py`,
`delivery.py` and `render.py` are untouched and there is still exactly one
implementation of the scoring rules.

Run it here, and expose it with a Cloudflare Tunnel:

    set JOBSTASH_PY_TOKEN=<the same secret the Worker holds>
    python py_server.py
    cloudflared tunnel --url http://localhost:3300

The tunnel dials *out*, so this keeps the property the architecture was built
on: this machine never accepts an inbound connection and no firewall port is
opened.

Endpoints (all but /healthz require the bearer token):

    GET  /healthz                      -> {"ok": true}
    GET  /stats                        -> pool counts
    POST /parse    ?name=<filename>    body = the raw resume bytes
    POST /trial    ?name=<filename>    body = the raw resume bytes
    POST /preview  body {"user_id": …}
    POST /deliver  body {"user_id": …}
"""
import os, sys, json, secrets, tempfile, traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import api_bridge

PORT = int(os.environ.get("JOBSTASH_PY_PORT", "3300"))
TOKEN = os.environ.get("JOBSTASH_PY_TOKEN", "")
# Matches the cap the upload routes enforce. Checked here too: this endpoint is
# reachable from the public internet through the tunnel, so it cannot rely on
# the caller having already checked anything.
MAX_BYTES = 8 * 1024 * 1024
ALLOWED_EXT = (".pdf", ".docx", ".txt", ".md")


class Handler(BaseHTTPRequestHandler):
    server_version = "jobstash"
    sys_version = ""

    # -- plumbing ----------------------------------------------------------
    def _send(self, obj, status=200):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authed(self):
        """Constant-time bearer check.

        `==` on a secret leaks its prefix through timing to anyone who can call
        this, and through the tunnel that is anyone at all.
        """
        header = self.headers.get("Authorization", "")
        prefix = "Bearer "
        if not header.startswith(prefix):
            return False
        return secrets.compare_digest(header[len(prefix):], TOKEN)

    def _body(self, limit=MAX_BYTES):
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if n <= 0:
            return b""
        if n > limit:
            return None
        return self.rfile.read(n)

    def log_message(self, fmt, *args):
        # One line per request, to stdout, without the client address - the
        # only caller is the Worker and its IP is noise.
        sys.stdout.write("[py] %s\n" % (fmt % args))
        sys.stdout.flush()

    # -- routing -----------------------------------------------------------
    def do_GET(self):
        route = urlparse(self.path).path.rstrip("/") or "/"
        if route == "/healthz":
            return self._send({"ok": True})
        if not self._authed():
            return self._send({"ok": False, "error": "unauthorised"}, 401)
        if route == "/stats":
            return self._dispatch(["stats"])
        self._send({"ok": False, "error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        route = parsed.path.rstrip("/") or "/"
        if not self._authed():
            return self._send({"ok": False, "error": "unauthorised"}, 401)

        if route in ("/parse", "/trial"):
            return self._file_command(route.lstrip("/"), parsed)

        if route in ("/preview", "/deliver"):
            raw = self._body(limit=64 * 1024)
            if raw is None:
                return self._send({"ok": False, "error": "bad request"}, 400)
            try:
                user_id = (json.loads(raw or b"{}") or {}).get("user_id")
            except ValueError:
                return self._send({"ok": False, "error": "bad JSON"}, 400)
            if not isinstance(user_id, str) or not user_id:
                return self._send({"ok": False, "error": "user_id required"}, 400)
            return self._dispatch([route.lstrip("/"), user_id])

        self._send({"ok": False, "error": "not found"}, 404)

    # -- commands ----------------------------------------------------------
    def _file_command(self, cmd, parsed):
        """`parse` and `trial` both take a resume file and nothing else."""
        name = (parse_qs(parsed.query).get("name") or ["resume.pdf"])[0]
        # The filename only ever chooses a parser and is echoed nowhere, but it
        # arrives from the network, so strip any path from it rather than trust
        # it near a tempfile name.
        name = os.path.basename(name.replace("\\", "/")) or "resume.pdf"
        ext = os.path.splitext(name)[1].lower()
        if ext not in ALLOWED_EXT:
            return self._send(
                {"ok": False,
                 "error": "We can read %s files." % ", ".join(ALLOWED_EXT)}, 400)

        raw = self._body()
        if raw is None:
            return self._send({"ok": False, "error": "That file is over 8MB."}, 413)
        if not raw:
            return self._send({"ok": False, "error": "No file received."}, 400)

        # The parser reads a path, so the bytes land in the OS temp dir and are
        # deleted in the finally block whatever happens. Nothing a visitor
        # uploads is kept - that was true of the old route and stays true here.
        fd, tmp = tempfile.mkstemp(prefix="jobstash-", suffix=ext)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(raw)
            self._dispatch([cmd, tmp, name])
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def _dispatch(self, argv):
        try:
            payload, code = api_bridge.run(argv)
        except Exception as e:
            # run() catches its own, so reaching here means the bridge itself
            # is broken. Log the traceback, answer without it: this response
            # crosses the public internet.
            traceback.print_exc()
            return self._send(
                {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}, 500)
        # The command's own exit code is not the HTTP status: "no profile" and
        # "that PDF has no text layer" are answers, not transport failures, and
        # the Worker reads `ok` to tell them apart.
        self._send(payload, 200 if code == 0 else 200)


def main():
    if not TOKEN:
        sys.stderr.write(
            "JOBSTASH_PY_TOKEN is not set.\n\n"
            "This server is published to the internet by the tunnel, and\n"
            "/deliver will mail a digest for any user id it is handed. It\n"
            "refuses to start without a shared secret rather than come up\n"
            "open to anyone who finds the hostname.\n")
        raise SystemExit(2)
    if len(TOKEN) < 32:
        sys.stderr.write("JOBSTASH_PY_TOKEN is under 32 characters; use a longer one.\n")
        raise SystemExit(2)

    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    # Bound to loopback on purpose. The tunnel connects to it from this same
    # machine, so binding 0.0.0.0 would expose it to the LAN for no gain.
    print("[py] listening on http://127.0.0.1:%d" % PORT)
    print("[py] storage: %s" % ("Cloudflare D1" if _d1() else "local jobstash.db"))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[py] stopped")


def _d1():
    import d1
    return d1.configured()


if __name__ == "__main__":
    main()
