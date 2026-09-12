# -*- coding: utf-8 -*-
"""
Create a demo account from a real resume so the pipeline can be exercised
end to end without going through the website.

    python seed_demo.py <resume.pdf> <email> [plan]
"""
import os, sys, json, io, datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db, resume_parse as R

PLAN_DAYS = {"one_time": 1, "three_day": 3, "seven_day": 7}


def seed(resume_path, email, plan="seven_day", password="demo1234"):
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

    today = datetime.date.today()
    ends = today + datetime.timedelta(days=PLAN_DAYS.get(plan, 7) - 1)
    conn.execute("UPDATE entitlements SET status='superseded' WHERE user_id=?",
                 (uid,))
    conn.execute(
        "INSERT INTO entitlements (id,user_id,plan,starts_on,ends_on,"
        "deliveries_used,status,created_at) VALUES (?,?,?,?,?,0,'active',?)",
        (db.new_id("ent_"), uid, plan, today.isoformat(), ends.isoformat(),
         db.now_iso()))
    conn.commit()
    conn.close()
    return uid, diag


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: python seed_demo.py <resume> <email> [plan]")
        raise SystemExit(2)
    plan = sys.argv[3] if len(sys.argv) > 3 else "seven_day"
    uid, diag = seed(sys.argv[1], sys.argv[2], plan)
    print("user      ", uid, sys.argv[2], "/", plan)
    print("families  ", diag["families"])
    print("years     ", diag["years"], "relevant /", diag["total_years"], "total")
    print("level     ", diag["level"], "| country", diag["country"])
    print("skills    ", diag["skills_found"], diag["top_skills"][:10])
