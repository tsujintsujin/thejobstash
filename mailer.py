# -*- coding: utf-8 -*-
"""
Delivery of the digest.

Two backends. The default writes a real RFC-822 message with the PDF attached
into outbox/ and returns "outbox" - no account, no key, no risk of mailing a
stranger while the product is still being built. Setting JOBSTASH_RESEND_KEY
switches to Resend and actually sends.

The outbox path is not a stub: the .eml it writes is a complete message that
opens in any mail client, so what gets tested locally is the thing that will
land in an inbox.

Note for when sending is switched on: email IS the product here, so a verified
sending domain with SPF, DKIM and DMARC has to be in place first. A young
domain mailing PDF attachments to strangers is the exact shape spam filters
are built to catch.
"""
import os, sys, base64, mimetypes, datetime, json
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OUT_DIR = os.environ.get("JOBSTASH_OUT",
                         os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "outbox"))
RESEND_KEY = os.environ.get("JOBSTASH_RESEND_KEY", "")
FROM_ADDR = os.environ.get("JOBSTASH_FROM", "TheJobStash <digest@thejobstash.local>")


def subject_for(summary):
    n = summary["matches"]
    if summary["first_ever"]:
        return "Your first sweep: %d matches" % n
    if summary["thin"]:
        return "A quiet run - %d match%s, and what came close" % (
            n, "" if n == 1 else "es")
    return "%d job%s matched your resume" % (n, "" if n == 1 else "s")


def _build_message(to_addr, subject, html_body, pdf_path):
    msg = EmailMessage()
    msg["From"] = FROM_ADDR
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="thejobstash.local")
    msg.set_content(
        "Your TheJobStash digest is attached, and rendered below in HTML.\n"
        "If you are reading this line, your mail client blocked the HTML "
        "version - open the attached PDF instead.\n")
    msg.add_alternative(html_body, subtype="html")

    if pdf_path and os.path.exists(pdf_path):
        ctype, _ = mimetypes.guess_type(pdf_path)
        maintype, subtype = (ctype or "application/pdf").split("/", 1)
        with open(pdf_path, "rb") as fh:
            msg.add_attachment(fh.read(), maintype=maintype, subtype=subtype,
                               filename=os.path.basename(pdf_path))
    return msg


def send(to_addr, subject, html_body, pdf_path=None, out_dir=None):
    """Returns (status, detail). status is 'sent', 'outbox' or 'failed'."""
    out_dir = out_dir or OUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    if RESEND_KEY:
        try:
            import requests
            payload = {"from": FROM_ADDR, "to": [to_addr],
                       "subject": subject, "html": html_body}
            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, "rb") as fh:
                    payload["attachments"] = [{
                        "filename": os.path.basename(pdf_path),
                        "content": base64.b64encode(fh.read()).decode("ascii")}]
            r = requests.post("https://api.resend.com/emails", json=payload,
                              headers={"Authorization": "Bearer " + RESEND_KEY},
                              timeout=30)
            if r.status_code < 300:
                return "sent", r.json().get("id", "")
            return "failed", "resend %d: %s" % (r.status_code, r.text[:200])
        except Exception as e:
            return "failed", "%s: %s" % (type(e).__name__, e)

    msg = _build_message(to_addr, subject, html_body, pdf_path)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe = "".join(c for c in to_addr if c.isalnum() or c in ".-_@")[:40]
    path = os.path.join(out_dir, "mail-%s-%s.eml" % (safe, stamp))
    with open(path, "wb") as fh:
        fh.write(bytes(msg))
    return "outbox", path
