# -*- coding: utf-8 -*-
"""
Re-hash stored passwords to the iteration count Cloudflare Workers allows.

    python scripts/rehash_passwords.py --dry
    python scripts/rehash_passwords.py

Why this exists: every hash written before the move used 120,000 PBKDF2
iterations, and workerd refuses anything above 100,000 outright
("NotSupportedError: iteration counts above 100000 are not supported"). A hash
it cannot compute is a hash it cannot verify, so those accounts could not sign
in at all - not "wrong password", just permanently shut out.

A hash cannot be converted without the plaintext, so this only re-hashes
accounts whose password is known: the seeded demo accounts documented in
README (demo1234) and the e2e throwaways that share it. Anything else is
listed and left alone - it needs a real password reset, which is a flow this
product does not have yet.

Reads D1 through the site's own endpoint, exactly like db.py does.
"""
import argparse, io, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

# .env.cloudflare holds the shared secret and the site origin.
envfile = os.path.join(ROOT, ".env.cloudflare")
if os.path.exists(envfile):
    for k, v in re.findall(r"^([A-Z0-9_]+)=(.*)$", io.open(envfile, encoding="utf-8").read(), re.M):
        if v and k not in os.environ:
            os.environ[k] = v

import db  # noqa: E402

# The documented demo password. Every seeded and e2e account uses it.
KNOWN = "demo1234"
KNOWN_PATTERNS = (r"@demo\.test$", r"^browser\.demo@", r"@example\.com$")


def known_account(email):
    return any(re.search(p, email) for p in KNOWN_PATTERNS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="show what would change")
    args = ap.parse_args()

    conn = db.init()
    rows = conn.execute(
        "SELECT id,email,password_hash FROM users WHERE password_hash IS NOT NULL"
    ).fetchall()

    stale = [r for r in rows
             if not r["password_hash"].startswith("pbkdf2$%d$" % db.PBKDF2_ROUNDS)]
    print("users with a password : %d" % len(rows))
    print("stale (wrong rounds)  : %d" % len(stale))
    print("target rounds         : %d\n" % db.PBKDF2_ROUNDS)

    fixed, manual = 0, []
    for r in stale:
        if not known_account(r["email"]):
            manual.append(r["email"])
            continue
        if args.dry:
            print("  would re-hash  %s" % r["email"])
        else:
            conn.execute("UPDATE users SET password_hash=? WHERE id=?",
                         (db.hash_password(KNOWN), r["id"]))
            print("  re-hashed      %s" % r["email"])
        fixed += 1

    conn.commit()
    conn.close()

    print("\n%d account(s) %s to the documented demo password."
          % (fixed, "would be reset" if args.dry else "reset"))
    if manual:
        print("\nLeft alone - the password is not known, so these cannot be")
        print("re-hashed and must be set deliberately:")
        for e in manual:
            print("   %s" % e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
