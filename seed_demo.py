# -*- coding: utf-8 -*-
"""
Create a demo account from a real resume so the pipeline can be exercised
end to end without going through the website.

    python seed_demo.py <resume.pdf> <email> [credits]

The account gets the one free credit every account starts with, unless a
number is given.
"""
import os, sys, json, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db, resume_parse as R


def seed(resume_path, email, credits=None, password="demo1234"):
    conn = db.init()
    text = R.extract_text(resume_path, resume_path)
    profile, diag = R.parse_profile(text)

    row = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if row:
        uid = row["id"]
    else:
        uid = db.new_id("usr_")
        conn.execute("INSERT INTO users (id,email,password_hash,created_at) "
                     "VALUES (?,?,?,?)",
                     (uid, email, db.hash_password(password), db.now_iso()))

    profile.user_id = uid
    conn.execute(
        "INSERT INTO profiles (user_id,resume_name,resume_text,profile_json,"
        "updated_at) VALUES (?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET "
        "resume_name=excluded.resume_name, resume_text=excluded.resume_text, "
        "profile_json=excluded.profile_json, updated_at=excluded.updated_at",
        (uid, os.path.basename(resume_path), text[:20000],
         json.dumps(R.profile_to_dict(profile)), db.now_iso()))

    if credits is not None:
        conn.execute("UPDATE users SET credits=? WHERE id=?", (credits, uid))
    conn.commit()
    conn.close()
    return uid, diag


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: python seed_demo.py <resume> <email> [credits]")
        raise SystemExit(2)
    credits = int(sys.argv[3]) if len(sys.argv) > 3 else None
    uid, diag = seed(sys.argv[1], sys.argv[2], credits)
    print("user      ", uid, sys.argv[2], "/ credits:",
          "default" if credits is None else credits)
    print("families  ", diag["families"])
    print("years     ", diag["years"], "relevant /", diag["total_years"], "total")
    print("level     ", diag["level"], "| country", diag["country"])
    print("skills    ", diag["skills_found"], diag["top_skills"][:10])
