# -*- coding: utf-8 -*-
"""
Pull a readable summary, responsibilities and requirements out of a scraped
job description.

Written against what the boards actually return, which is worse than you would
hope:

  * some descriptions still carry raw HTML (`<div class="content-intro"><p>`)
    even though sources.py strips most of it
  * mojibake is common - a cp1252 smart quote round-tripped through utf-8
    arrives as a replacement character mid-sentence
  * bullet lists are flattened. "In this role you will: Design, architect and
    implement X Extend and maintain Y Develop Z" was a <ul> once, and there is
    no newline or bullet character left to split on
  * the salary field is empty on most rows, but the figure is frequently
    sitting in the description text

So this does not parse structure - there is none. It finds heading phrases,
then re-splits the run-on prose on sentence ends and on capitalised action
verbs, which is where the <li> boundaries used to be.
"""
import re

# ---------------------------------------------------------------------------
# cleaning
# ---------------------------------------------------------------------------

_TAG = re.compile(r"<[^>]{1,400}>")
_ENTITY = {
    "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'",
    "&apos;": "'", "&nbsp;": " ", "&ndash;": "-", "&mdash;": "-",
    "&rsquo;": "'", "&lsquo;": "'", "&ldquo;": '"', "&rdquo;": '"',
    "&hellip;": "...", "&bull;": " ",
}
# cp1252 bytes decoded as utf-8 and back again. Left alone these show up as
# black diamonds in the middle of otherwise fine sentences.
_MOJI = {
    "â": "'", "â": "'",
    "â": '"', "â": '"',
    "â": "-", "â": "-",
    "â¦": "...", "Â ": " ",
    "�": "'",
}


def clean(text):
    """HTML out, mojibake out, whitespace collapsed."""
    if not text:
        return ""
    s = str(text)
    for bad, good in _MOJI.items():
        s = s.replace(bad, good)
    s = _TAG.sub(" ", s)
    for ent, ch in _ENTITY.items():
        s = s.replace(ent, ch)
    s = re.sub(r"&[a-z]{2,8};", " ", s)
    s = s.replace("•", " ").replace("·", " ")
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------------------
# salary
# ---------------------------------------------------------------------------

_CUR = r"(?:\$|USD|US\$|EUR|GBP|CAD|AUD|PHP|SGD|€|£|₱)"

# A salary, not a funding round. Guarded against "$3.7B valuation" and
# "$570M raised", which appear in roughly every startup's boilerplate.
_SALARY_PATTERNS = [
    # $120,000 - $150,000
    re.compile(_CUR + r"\s?\d{2,3},\d{3}\s*(?:-|to|–|—)\s*"
               + _CUR + r"?\s?\d{2,3},\d{3}", re.I),
    # $120k - $150k
    re.compile(_CUR + r"\s?\d{2,3}\s?k\s*(?:-|to|–|—)\s*"
               + _CUR + r"?\s?\d{2,3}\s?k", re.I),
    # $178,500
    re.compile(_CUR + r"\s?\d{2,3},\d{3}(?!\s*(?:m|b|million|billion))", re.I),
    # 120,000 USD
    re.compile(r"\d{2,3},\d{3}\s*(?:USD|EUR|GBP|PHP|CAD|AUD)", re.I),
    # $65 / hour
    re.compile(_CUR + r"\s?\d{2,3}\s*(?:/|per\s+)\s?(?:hour|hr)", re.I),
    # $120k
    re.compile(_CUR + r"\s?\d{2,3}\s?k\b(?!\s*(?:m|b))", re.I),
]

_SALARY_NEGATIVE = re.compile(
    r"(raised|valuation|valued at|funding|acquired|revenue|arr|market cap|"
    r"investors?|series [a-f]\b)", re.I)


_SYMBOL = {"usd": "$", "us$": "$", "eur": "€", "gbp": "£", "php": "₱",
           "cad": "C$", "aud": "A$", "sgd": "S$", "inr": "₹"}
_RANGE_RAW = re.compile(
    r"^\s*([A-Za-z$€£₱]{1,4})?\s*([\d][\d,]*(?:\.\d+)?)\s*(?:-|to|–|—)\s*"
    r"([A-Za-z$€£₱]{1,4})?\s*([\d][\d,]*(?:\.\d+)?)\s*(.*)$")


def _num(s):
    try:
        return float(str(s).replace(",", ""))
    except ValueError:
        return None


def format_salary(raw):
    """Make a board's salary string readable without inventing a period.

    Boards emit things like "USD 92359.68 to 133409". Commas and a symbol fix
    the readability; the pay period is deliberately NOT guessed, because a
    range of 60-70 is hourly and a range of 80000-85000 is annual and there is
    nothing in the string that reliably says which.
    """
    if not raw:
        return None
    s = re.sub(r"\s+", " ", str(raw)).strip()
    m = _RANGE_RAW.match(s)
    if not m:
        return s
    cur, lo_s, cur2, hi_s, tail = m.groups()
    lo, hi = _num(lo_s), _num(hi_s)
    if lo is None or hi is None:
        return s

    token = (cur or cur2 or "").strip().lower()
    sym = _SYMBOL.get(token, token.upper() if token.isalpha() else token)
    fmt = lambda n: "{:,}".format(int(round(n)))
    body = ("%s%s - %s%s" % (sym, fmt(lo), sym, fmt(hi)) if sym in _SYMBOL.values()
            else "%s %s - %s" % (sym, fmt(lo), fmt(hi)) if sym
            else "%s - %s" % (fmt(lo), fmt(hi)))
    tail = (tail or "").strip()
    return (body + " " + tail).strip() if tail else body


def find_salary(field, description):
    """The salary field if the board gave one, else mine the description.

    Most rows have an empty salary field while the figure sits in the body, so
    not looking there throws away information the posting actually published.
    """
    if field and str(field).strip():
        return format_salary(str(field).strip()), "listed"

    text = clean(description)
    if not text:
        return None, "none"

    for pat in _SALARY_PATTERNS:
        for m in pat.finditer(text):
            window = text[max(0, m.start() - 90): m.end() + 40]
            if _SALARY_NEGATIVE.search(window):
                continue          # company money, not the candidate's
            return m.group(0).strip(), "from description"
    return None, "none"


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------

_RESP_HEAD = re.compile(
    r"\b(responsibilities|what you.?ll (?:do|be doing)|what you will do|"
    r"in this role(?:,? you will)?|your role|the role|day.to.day|duties|"
    r"you will|key accountabilities|about the role|what the job involves)\b"
    r"\s*[:\-–]?\s*", re.I)

_REQ_HEAD = re.compile(
    r"\b(requirements|qualifications|what you.?ll need|what you need|"
    r"what we.?re looking for|who you are|about you|your profile|"
    r"must have|minimum qualifications|skills? (?:and|&) experience|"
    r"we.?re looking for|you should have|required skills|"
    r"basic qualifications|experience required)\b\s*[:\-–]?\s*", re.I)

# Anything that means the useful part is over.
_STOP_HEAD = re.compile(
    r"\b(benefits|perks|what we offer|compensation|salary|why join|"
    r"our culture|equal opportunit|about (?:us|the company)|how to apply|"
    r"interview process|nice to have|bonus points|diversity)\b", re.I)

# Where a <li> boundary probably used to be: a lowercase word or bracket
# followed by a capitalised action verb.
# Imperative verbs only. The noun forms have to be excluded explicitly or
# "Adobe Experience Manager" splits at "Manager" and "Developer experience"
# splits at "Developer" - both were happening on real postings.
_VERBS = (r"Design(?!er)|Develop(?!er)|Build(?!er)|Create|Implement|"
          r"Maintain|Manage(?!r|ment)|Own(?!er)|Lead(?!er)|Collaborate|"
          r"Work(?!er)|Partner(?!ship)|Support(?!ing)|Ensure|Drive(?!r)|"
          r"Deliver(?!y|able)|Write(?!r)|Test(?!er|ing)|Deploy|"
          r"Monitor(?!ing)|Analyz|Analys|Optimi|Improve|Contribute|"
          r"Participate|Coordinate|Review(?!er)|Translate|Define|Establish|"
          r"Provide(?!r)|Research(?!er)|Troubleshoot|Debug|Document(?!ation)|"
          r"Mentor(?!ing)|Communicate|Identify|Track(?!er|ing)|Prepare|"
          r"Execute|Handle|Assist|Perform|Respond|Report(?!ing)")
_BULLET_SPLIT = re.compile(r"(?<=[a-z\),\.])\s+(?=(?:%s)(?:e|es|s|ing|d)?\b)" % _VERBS)


def _split_items(chunk):
    """Turn a run of prose back into the list it used to be."""
    chunk = chunk.strip(" :;-–")
    if not chunk:
        return []

    # Real bullets survive occasionally - prefer them when they do.
    parts = [p for p in re.split(r"\s*[•·\*‣●]\s*|\n+", chunk)
             if len(p.strip()) > 24]
    if len(parts) < 2:
        parts = [chunk]

    items = []
    for p in parts:
        for piece in _BULLET_SPLIT.split(p):
            for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])", piece):
                s = sentence.strip(" .;,-–")
                if 24 <= len(s) <= 400:
                    items.append(s)
    return items


# Hacker News "who is hiring" entries are whole comments listing many roles,
# so their "requirements" come out as a pile of apply-links. Anything that is
# mostly URL or list punctuation is not a sentence somebody wants to read.
_JUNK = re.compile(r"https?://|www\.|@\w+\.\w+", re.I)


def _is_junk(s):
    if _JUNK.search(s):
        return True
    # A leftover sub-heading, not a bullet: "Your key responsibilities:
    # Technical" is the label plus the first word of the item after it.
    if s.rstrip().endswith(":") or len(s.strip()) < 30:
        return True
    if re.match(r"^[A-Z][\w &/]{0,28}:\s*\w{0,12}$", s.strip()):
        return True
    letters = sum(c.isalpha() or c.isspace() for c in s)
    if not s or letters / len(s) < 0.72:
        return True
    return s.count("|") > 1 or s.count("+") > 1


def _tidy(item, limit=165):
    s = re.sub(r"\s+", " ", item).strip(" .;,-–")
    if len(s) > limit:
        cut = s[:limit].rsplit(" ", 1)[0]
        s = cut.rstrip(" .,;-") + "…"
    return s[:1].upper() + s[1:] if s else s


def _find_head(text, head_re):
    """First occurrence that is really a heading, not the same word mid-clause.

    "Translate business requirements into technical plans" contains the word
    "requirements", and matching it started the requirements section halfway
    through a sentence - the extracted bullet literally began "Into technical
    plans". A heading either follows sentence-ending punctuation or carries a
    colon; anything else is prose.
    """
    for m in head_re.finditer(text):
        before = text[:m.start()].rstrip()
        if not before or before[-1] in ".:;!?)…":
            return m
        if ":" in m.group(0):
            return m
    return None


def _section(text, head_re, max_items=4):
    m = _find_head(text, head_re)
    if not m:
        return []
    rest = text[m.end():]
    stop = _find_head(rest, _STOP_HEAD)
    other = (_find_head(rest, _REQ_HEAD) if head_re is _RESP_HEAD
             else _find_head(rest, _RESP_HEAD))
    end = min([x.start() for x in (stop, other) if x] + [1400])
    items, seen = [], set()
    for it in _split_items(rest[:end]):
        if _is_junk(it):
            continue
        t = _tidy(it)
        key = t.lower()[:50]
        if t and key not in seen:
            seen.add(key)
            items.append(t)
        if len(items) >= max_items:
            break
    return items


def summarise(description, salary_field=None, max_items=4):
    """Everything the job card needs beyond the title.

    Returns summary (a sentence or two), responsibilities, requirements, and a
    salary that is never blank - "Salary undisclosed" is information too.
    """
    text = clean(description)
    salary, salary_src = find_salary(salary_field, description)

    resp = _section(text, _RESP_HEAD, max_items)
    reqs = _section(text, _REQ_HEAD, max_items)

    # The opening lines, up to wherever the first heading starts.
    first = min([m.start() for m in
                 (_find_head(text, _RESP_HEAD), _find_head(text, _REQ_HEAD),
                  _find_head(text, _STOP_HEAD)) if m] + [len(text)])
    intro = text[:first].strip()
    sentences = re.split(r"(?<=[.!?])\s+", intro)
    summary = ""
    for s in sentences:
        if len(summary) + len(s) > 300:
            break
        summary = (summary + " " + s).strip()
    if not summary:
        summary = _tidy(text, 260)

    return {
        "summary": summary or None,
        "responsibilities": resp,
        "requirements": reqs,
        "salary": salary or "Salary undisclosed",
        "salary_known": bool(salary),
        "salary_source": salary_src,
    }


if __name__ == "__main__":
    import sqlite3, os, sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "jobstash.db"))
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    rows = conn.execute("SELECT title,salary,description FROM jobs "
                        "WHERE length(description)>700 ORDER BY RANDOM() "
                        "LIMIT ?", (n,)).fetchall()
    for title, sal, desc in rows:
        d = summarise(desc, sal)
        print("=" * 72)
        print(title)
        print("  salary :", d["salary"], "(%s)" % d["salary_source"])
        print("  summary:", (d["summary"] or "")[:200])
        for label, key in (("resp", "responsibilities"), ("reqs", "requirements")):
            for i, it in enumerate(d[key]):
                print("  %s: %s" % (label if i == 0 else "    ", it))
        print()
