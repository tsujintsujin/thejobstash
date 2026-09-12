# -*- coding: utf-8 -*-
"""
Regenerate web/migrations/0001_init.sql from db.py's SCHEMA.

db.py stays the single source of truth for the table shape. Hand-maintaining a
second copy of it for D1 is exactly how the two ends start disagreeing about
what a column is called, so this derives one from the other instead.

    python scripts/gen_migration.py
"""
import io, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PY = os.path.join(HERE, "..", "..", "db.py")
OUT = os.path.join(HERE, "..", "migrations", "0001_init.sql")


def main():
    src = io.open(DB_PY, encoding="utf-8").read()

    schema = re.search(r'SCHEMA = """(.*?)"""', src, re.S).group(1)
    # D1 manages its own journalling; PRAGMA is neither needed nor permitted.
    schema = schema.replace("PRAGMA journal_mode=WAL;\n", "")

    post = re.search(r"POST_MIGRATIONS = \[\n(.*?)\]", src, re.S).group(1)
    idx = "".join(re.findall(r'"([^"]*)"', post))

    out = (
        "-- Generated from db.py's SCHEMA. db.py stays the single source of "
        "truth for\n-- the shape; this file is what wrangler applies to D1.\n"
        "-- Regenerate with: npm run migration:gen\n"
        + schema.rstrip()
        + "\n\n-- Added after the first databases existed. A SQLite UNIQUE "
        "index permits any\n-- number of NULLs, which is what makes it "
        "correct: every password-only\n-- account has a NULL google_sub and "
        "none of them collide.\n" + idx + ";\n"
    )
    io.open(OUT, "w", encoding="utf-8").write(out)
    print("wrote %s (%d tables)" % (
        os.path.normpath(OUT),
        len(re.findall(r"CREATE TABLE IF NOT EXISTS", out))))


if __name__ == "__main__":
    main()
