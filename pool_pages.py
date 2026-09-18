# -*- coding: utf-8 -*-
"""
The public /jobs pages' data: one D1 row per role family.

Search engines find a job site through pages about kinds of work ("virtual
assistant jobs", "remote jobs Philippines"), and the site had none. This
pushes what those pages need and nothing more: counts, and a dozen example
postings per family. The pool itself never leaves this machine
(see db.jobs_conn()), the same deal as pool_stats.

Only postings a Filipino job seeker could take are counted: located in the
Philippines, or remote. A Berlin onsite role is in the pool for the scorer's
sake, but a page promising "accounting jobs" to this audience would be
padding its number with it.

    python pool_pages.py            print what would be pushed
    python pool_pages.py --push     push it to D1
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# slug, display name, title pattern. A posting can sit in several families: a
# "medical virtual assistant" belongs on both pages. `remote` matches the
# location instead of the title. Order is the order of the /jobs index.
FAMILIES = [
    ("remote", "Online and work-from-home", None),
    ("part-time", "Part-time", r"part[- ]?time|\bpart timer\b"),
    ("no-experience", "Entry-level and no-experience",
     r"entry[- ]level|no experience|fresh grad|\btrainee\b|\bjunior\b|"
     r"\bintern(ship)?\b|beginner"),
    ("non-voice", "Non-voice",
     r"non[- ]?voice|chat support|email support|chat (agent|moderator)|"
     r"e-?mail (agent|specialist)|back ?office|data entry"),
    ("virtual-assistant", "Virtual assistant",
     r"virtual assistant|\bva\b|executive assistant|personal assistant"),
    ("customer-service", "Customer service",
     r"customer (service|support|success|care)|\bcsr\b|call cent(er|re)|"
     r"contact cent(er|re)|chat support"),
    ("sales", "Sales and business development",
     r"\bsales\b|business development|account executive|appointment setter|"
     r"lead gen|telemarket"),
    ("marketing", "Marketing and social media",
     r"marketing|social media|\bseo\b|content creator|\bppc\b|ads specialist"),
    ("accounting", "Accounting and bookkeeping",
     r"accountant|accounting|bookkeep|payroll|finance|auditor|\bcpa\b|billing"),
    ("software-developer", "Software and web development",
     r"developer|software engineer|programmer|full[- ]?stack|front[- ]?end|"
     r"back[- ]?end|web dev|devops"),
    ("graphic-design", "Graphic design and video",
     r"graphic|\bdesigner\b|ui/ux|\bux\b|video editor|illustrat|animator"),
    ("writing", "Writing and content",
     r"writer|copywrit|\beditor\b|proofread|transcri"),
    ("admin", "Admin and data entry",
     r"administrative|admin assistant|office (staff|assistant)|data entry|"
     r"\bclerk\b|secretary|encoder"),
    ("hr-recruitment", "HR and recruitment",
     r"recruit|talent acquisition|\bhr\b|human resource"),
    ("project-manager", "Project and operations management",
     r"project manager|project coordinator|operations manager|product manager"),
    ("healthcare", "Healthcare and medical",
     r"\bnurse\b|nursing|medical|healthcare|pharmac|caregiver|dental|therap"),
    ("teaching", "Teaching and tutoring",
     r"teacher|tutor|\besl\b|instructor"),
    ("data-analyst", "Data and analytics",
     r"data analyst|data scien|analytics|business intelligence|data engineer"),
    ("it-support", "IT support",
     r"it support|help ?desk|service desk|system admin|network (engineer|admin)|"
     r"desktop support"),
]
_PATTERNS = {s: re.compile(p, re.I) for s, _, p in FAMILIES if p}

# Part-time, no experience and non-voice are how people in the Philippines
# search ("part time online jobs", "wfh no experience", "non voice"), but a
# title rarely says so. These families also read the posting's own text, and
# a senior title or an explicit "not entry-level" keeps a posting off.
_DESC = {s: re.compile(p, re.I) for s, p in [
    ("part-time",
     r"part[- ]?time job (summary|overview)|"
     r"(job|employment|work|position) type\s*:?\s*part[- ]?time|"
     r"type of work\s*:?\s*part[- ]?time|"
     r"\bpart[- ]?time (role|position|job|opportunity|contract)\b"),
    ("no-experience",
     r"no (prior |previous )?(work |sales )?experience (is )?(required|needed|necessary)|"
     r"fresh graduates? (are )?(welcome|may apply|can apply)|"
     r"open to fresh grad|entry[- ]level (role|position)"),
    ("non-voice", r"non[- ]?voice"),
]}
# A senior title keeps a posting off the no-experience page whatever its
# text says; the text can only rule itself out explicitly.
_NOT_TITLE = {"no-experience": re.compile(
    r"\bsenior\b|\bsr\b|\blead\b|manager|director|\bhead\b|experienced", re.I)}
_NOT_DESC = {"no-experience": re.compile(r"not an? entry[- ]level", re.I)}

REMOTE = re.compile(r"remote|work from home|\bwfh\b|anywhere|worldwide", re.I)
PH = re.compile(r"philippines|manila|cebu|davao|makati|taguig|quezon|pasig", re.I)

# A family below this is not pushed, so its page 404s and leaves the
# sitemap. Twenty-odd postings is not a page worth ranking; it is a thin one.
MIN_TOTAL = 25
EXAMPLES = 12
PER_BOARD = 4
FRESH_DAYS = 7


_ISO = re.compile(r"\d{4}-\d\d-\d\d")


def posted(job):
    """The board's own posting date when it gives an ISO one, else the day
    we first saw it. first_seen alone reads as "everything is new": the pool
    was rebuilt on 2026-09-10 and every row got that date."""
    p = (job.get("posted") or "")[:10]
    return p if _ISO.fullmatch(p) else (job.get("first_seen") or "")[:10]


# Some boards hand back an id where the employer should be (OnlineJobs.ph
# hides employers from logged-out readers). Printing "onlinejobs-1732218" on a
# public page reads as broken, so it is dropped and the board is shown instead.
_PLACEHOLDER_CO = re.compile(r"[a-z]+-\d+")
# Pay is shown only when it says what it is. "650" alone could be pesos a day
# or dollars a month; a page that guesses is worse than one that says nothing.
_PAY_UNIT = re.compile(r"[₱$€£]|\b(php|usd|eur|gbp)\b|hour|/hr|month|year|annum|week|day",
                       re.I)


def company(job):
    c = (job.get("company") or "").strip()
    return "" if _PLACEHOLDER_CO.fullmatch(c) else c


def pay(job):
    s = (job.get("salary") or "").strip()
    # Kalibrr converts some USD pay to PHP and prints the float whole:
    # "PHP 354.51495346088495 to 455.80494016399496".
    s = re.sub(r"(\d)\.\d{3,}", r"\1", s)
    return s if _PAY_UNIT.search(s) else ""


def is_remote(job):
    return bool(REMOTE.search((job.get("location") or "") + " " +
                              (job.get("title") or "")))


def eligible(job):
    """In the Philippines, or remote. Everything else is off these pages."""
    return is_remote(job) or bool(PH.search(job.get("location") or ""))


def families_of(job):
    """Every family slug a posting belongs to."""
    out = ["remote"] if is_remote(job) else []
    title = job.get("title") or ""
    desc = job.get("description") or ""
    for s, p in _PATTERNS.items():
        if not (p.search(title) or (s in _DESC and _DESC[s].search(desc))):
            continue
        if s in _NOT_TITLE and _NOT_TITLE[s].search(title):
            continue
        if s in _NOT_DESC and _NOT_DESC[s].search(desc):
            continue
        out.append(s)
    return out


def build(jobs, fresh_since):
    """Rows for pool_pages from an iterable of job dicts.

    `fresh_since` is a YYYY-MM-DD date; a posting posted on or after it
    counts as new this week. Examples prefer postings that state pay, then
    the newest, one per title so the list shows the range of the work.
    """
    names = {s: n for s, n, _ in FAMILIES}
    acc = {s: {"total": 0, "fresh": 0, "remote": 0, "with_pay": 0, "pool": []}
           for s in names}
    for j in jobs:
        if not eligible(j):
            continue
        for s in families_of(j):
            a = acc[s]
            a["total"] += 1
            a["fresh"] += posted(j) >= fresh_since
            a["remote"] += is_remote(j)
            a["with_pay"] += bool(pay(j))
            a["pool"].append(j)

    rows = []
    for s, _, _ in FAMILIES:
        a = acc[s]
        if a["total"] < MIN_TOTAL:
            continue
        ranked = sorted(a["pool"], key=lambda j: (bool(pay(j)), posted(j)),
                        reverse=True)
        seen, per_board, picked = set(), {}, []
        # Two passes: the first caps each board so one prolific board cannot
        # fill the whole list, the second tops up if a family has few boards.
        for cap in (PER_BOARD, EXAMPLES):
            for j in ranked:
                if len(picked) == EXAMPLES:
                    break
                key = re.sub(r"\W+", " ", (j.get("title") or "").lower()).strip()
                src = j.get("source") or ""
                if key in seen or per_board.get(src, 0) >= cap:
                    continue
                seen.add(key)
                per_board[src] = per_board.get(src, 0) + 1
                picked.append(j)
        ex = []
        for j in sorted(picked, key=lambda j: (bool(pay(j)), posted(j)),
                        reverse=True):
            ex.append({
                "title": (j.get("title") or "")[:120],
                "company": company(j)[:80],
                "source": j.get("source") or "",
                "location": (j.get("location") or "")[:80],
                "salary": pay(j)[:60],
                "posted": posted(j),
            })
        rows.append({"slug": s, "name": names[s], "total": a["total"],
                     "fresh": a["fresh"], "remote": a["remote"],
                     "with_pay": a["with_pay"],
                     "examples": json.dumps(ex, ensure_ascii=False)})
    return rows


def compute():
    import datetime, db, ingest
    since = (datetime.datetime.now(datetime.timezone.utc)
             - datetime.timedelta(days=FRESH_DAYS)
             ).strftime("%Y-%m-%d")
    jobs = (dict(r) for r in db.jobs_conn().execute(
        "SELECT title,company,source,location,salary,posted,first_seen,description "
        "FROM jobs WHERE "
        + ingest.SCORED))
    return build(jobs, since)


def push(rows=None):
    """Upsert every family, then drop the ones that fell under MIN_TOTAL.

    Upsert rather than delete-then-insert: between the two a page would 404,
    and a crawler that lands in that gap drops the page from the index.
    """
    import db
    rows = compute() if rows is None else rows
    conn = db.init()
    now = db.now_iso()
    for r in rows:
        conn.execute(
            "INSERT OR REPLACE INTO pool_pages "
            "(slug,name,total,fresh,remote,with_pay,examples,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (r["slug"], r["name"], r["total"], r["fresh"], r["remote"],
             r["with_pay"], r["examples"], now))
    keep = [r["slug"] for r in rows]
    if keep:
        conn.execute("DELETE FROM pool_pages WHERE slug NOT IN (%s)"
                     % ",".join("?" * len(keep)), keep)
    conn.commit()
    conn.close()
    return rows


def _check():
    """The rules that would fail silently. Run: python pool_pages.py --test"""
    j = lambda t, loc, **k: dict(title=t, location=loc, **k)
    assert families_of(j("Medical Virtual Assistant", "Philippines (remote)")) \
        == ["remote", "virtual-assistant", "healthcare"]
    assert families_of(j("Account Executive", "Makati")) == ["sales"]
    assert not eligible(j("Accountant", "Berlin"))
    # Families read from the posting's text, and what keeps a posting off them.
    assert "part-time" in families_of(j("Bookkeeper", "Cebu",
        description="Accounting Part time Job Summary: ..."))
    assert "no-experience" in families_of(j("Sales Agent", "Remote",
        description="No prior sales experience required."))
    assert "no-experience" not in families_of(j("Senior Accountant", "Remote",
        description="Fresh graduates welcome"))
    assert "no-experience" not in families_of(j("Credit VA", "Remote",
        description="This is not an entry-level position."))
    assert "non-voice" in families_of(j("CSR", "Pampanga", description="NON-VOICE account"))
    assert "non-voice" in families_of(j("Data Entry Clerk", "Manila"))
    assert eligible(j("Accountant", "Cebu City")) and eligible(j("Dev", "Worldwide"))
    base = [j("Bookkeeper %d" % i, "Philippines (remote)", company="C%d" % i,
              salary="" if i % 2 else "PHP 30000", first_seen="2026-09-0%d" % (i % 9 + 1))
            for i in range(30)]
    rows = {r["slug"]: r for r in build(base + base[:1], "2026-09-05")}
    acc = rows["accounting"]
    assert acc["total"] == 31 and acc["with_pay"] == 16
    ex = json.loads(acc["examples"])
    assert len(ex) == EXAMPLES and all(e["salary"] for e in ex)   # pay first
    assert len({e["title"] for e in ex}) == EXAMPLES               # deduped
    assert company({"company": "onlinejobs-1732218"}) == "" and \
        company({"company": "Acme Inc"}) == "Acme Inc"
    assert pay({"salary": "650"}) == "" and pay({"salary": "1000+"}) == ""
    assert pay({"salary": "₱35,000 – ₱50,000 per month"}) and \
        pay({"salary": "$4/hour"}) and pay({"salary": "PHP 15000 to 60000"})
    assert pay({"salary": "PHP 354.51495346088495 to 455.80494016399496"}) \
        == "PHP 354 to 455"
    assert "virtual-assistant" not in rows                       # under MIN_TOTAL
    assert posted({"posted": "Tue, 18 Aug", "first_seen": "2026-09-10T04:00Z"}) \
        == "2026-09-10" and posted({"posted": "2026-09-08"}) == "2026-09-08"
    print("pool_pages: ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--test" in sys.argv:
        _check()
    elif "--push" in sys.argv:
        for r in push():
            print(r["slug"], r["total"])
    else:
        for r in compute():
            print("%-20s total %5d  new %4d  remote %5d  pay %5d"
                  % (r["slug"], r["total"], r["fresh"], r["remote"], r["with_pay"]))
