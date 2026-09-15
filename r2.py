# -*- coding: utf-8 -*-
"""
Push a rendered digest up to the Worker, which stores it in R2.

The dashboard's download link is served by a Worker that has no disk and no
route to this machine, so the HTML and PDF that `render.write_digest()` writes
here have to go somewhere the Worker can read. That is R2.

Uploading *through the Worker* rather than straight to R2 is deliberate: the
S3-compatible endpoint would need request signing and a second set of
credentials, where the Worker already holds the bucket as a binding and
already shares a secret with this process. One secret, no signing, ~30 lines
on each side.

Best-effort by design. A failed upload must not lose a delivery that was
otherwise fine - the email with the PDF attached has usually already gone, and
that is the product. The row then keeps its local path and the dashboard's
download answers 410, which is the honest answer.
"""
import sys, os, urllib.request, urllib.error
from urllib.parse import quote

ORIGIN = os.environ.get("JOBSTASH_SITE_ORIGIN", "").rstrip("/")
TOKEN = os.environ.get("JOBSTASH_PY_TOKEN", "")

TYPES = {".html": "text/html; charset=utf-8", ".pdf": "application/pdf"}


def configured():
    return bool(ORIGIN and TOKEN)


def put(local_path, key, timeout=120):
    """Upload one file. Returns "r2:<key>" on success, None otherwise."""
    if not configured() or not local_path or not os.path.exists(local_path):
        return None

    ext = os.path.splitext(local_path)[1].lower()
    try:
        with open(local_path, "rb") as fh:
            body = fh.read()
        req = urllib.request.Request(
            "%s/api/internal/digest?key=%s" % (ORIGIN, quote(key, safe="")),
            data=body,
            headers={
                "Authorization": "Bearer " + TOKEN,
                "Content-Type": TYPES.get(ext, "application/octet-stream"),
                # See d1.py: Cloudflare's bot rules reject urllib's default.
                "User-Agent": "TheJobStash-scorer/1.0 (+https://thejobstash.com)",
            },
            method="PUT",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if 200 <= r.status < 300:
                return "r2:" + key
    except (urllib.error.URLError, OSError) as e:
        print("[r2] upload of %s failed: %s" % (key, e), file=sys.stderr)
    return None


def put_digest(user_id, delivery_id, html_path, pdf_path):
    """Upload one digest's pair. Returns the paths to store on the delivery row.

    Falls back to the local path for whichever half did not make it, so a
    partial failure still records where the file actually is.
    """
    base = "%s/%s" % (user_id, delivery_id)
    return (
        put(html_path, base + ".html") or html_path,
        put(pdf_path, base + ".pdf") or pdf_path,
    )
