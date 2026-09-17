# -*- coding: utf-8 -*-
"""
Any resume -> the Harvard format, laid out like Justin's own resume.

    python harvard.py --id <id> --json     what the n8n workflow runs
    python harvard.py <resume-file> [out-dir]

--id reads harvard/<id>.pdf|.docx|.txt and writes harvard/<id>-harvard.html
and .pdf beside it. The id is the only thing that reaches a shell, so it is
checked against a strict shape; the folder is fixed.

HOW IT WORKS
------------
1. Text comes out through resume_parse.extract_text(), the same reader the
   scorer uses.
2. Gemini turns that text into fixed JSON: header, education, experience,
   projects, activities, additional. It may tighten wording. It may not add
   a fact.
3. check_facts() holds it to that. Every number, organisation, school, title
   and skill in the output has to appear in the source. On a miss, Gemini
   is asked once more with the misses listed; whatever still fails is
   removed, not printed.
4. The HTML uses the CSS from JobHunt/resume/build_resume.py, which prints
   Justin's resumes. render._print_pdf() turns it into a PDF.

Soft-skill lists and summaries are left out on purpose, because the Harvard
format carries neither. A job with no dates keeps blank dates and a warning.
Nothing is ever guessed.
"""
import argparse, html, io, json, os, re, sys, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import resume_parse as R, render

DIR = os.environ.get("JOBSTASH_HARVARD_DIR") or os.path.join(HERE, "harvard")
# Tried in order. On the free tier each model has its own daily quota, so a
# 429 moves on to the next one. gemini-2.5 is closed to new keys.
MODELS = ("gemini-3.6-flash", "gemini-3.5-flash", "gemini-3-flash-preview",
          "gemini-3.5-flash-lite", "gemini-3.1-flash-lite")
USED = []
ID_RE = re.compile(r"^[a-z0-9_-]{1,64}$")


def api_key():
    k = os.environ.get("JOBSTASH_GEMINI_KEY")
    if k:
        return k
    # Looked for in the live checkout as well, so a git worktree works too.
    for d in (HERE, r"D:\AIO Freelance\TheJobStash"):
        p = os.path.join(d, ".env.gemini")
        if os.path.exists(p):
            m = re.search(r"^JOBSTASH_GEMINI_KEY=(.+)$", open(p, encoding="utf-8").read(), re.M)
            if m:
                return m.group(1).strip()
    raise RuntimeError("JOBSTASH_GEMINI_KEY is not set (.env.gemini)")


# ---------------------------------------------------------------------------
# text
# ---------------------------------------------------------------------------

def read_text(path):
    t = R.extract_text(path, path)
    if t.startswith("__PARSE_ERROR__"):
        raise ValueError("Could not read that file. PDF, DOCX and TXT are supported.")
    # Google Docs PDFs come out of pypdf one word per line ("JOHN\n \nFRANCIS").
    # Put the words back on their lines.
    t = t.replace("\n \n", " ")
    t = re.sub(r"[ \t]+", " ", t)
    if len(t.strip()) < 200:
        raise ValueError("Only %d characters could be read. If it is a scanned "
                         "PDF, export a text version." % len(t.strip()))
    return t


def norm(s):
    """Lowercased alphanumerics only, so 'Next.js' matches 'nextjs' and '–' matches '-'."""
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


# ---------------------------------------------------------------------------
# the model
# ---------------------------------------------------------------------------

_S, _A = {"type": "STRING"}, lambda item: {"type": "ARRAY", "items": item}
ENTRY = {"type": "OBJECT", "properties": {
    "org": _S, "location": _S, "title": _S, "dates": _S, "bullets": _A(_S)},
    "required": ["org", "location", "title", "dates", "bullets"]}
SCHEMA = {"type": "OBJECT", "properties": {
    "name": _S, "location": _S, "phone": _S, "email": _S, "links": _A(_S),
    "education": _A({"type": "OBJECT", "properties": {
        "school": _S, "location": _S, "degree": _S, "dates": _S, "details": _A(_S)},
        "required": ["school", "location", "degree", "dates", "details"]}),
    "experience": _A(ENTRY),
    "projects": _A({"type": "OBJECT", "properties": {
        "name": _S, "link": _S, "stack": _S, "dates": _S, "bullets": _A(_S)},
        "required": ["name", "link", "stack", "dates", "bullets"]}),
    "activities": _A(ENTRY),
    "additional": _A({"type": "OBJECT", "properties": {
        "label": _S, "items": _A(_S)}, "required": ["label", "items"]}),
}, "required": ["name", "location", "phone", "email", "links", "education",
                "experience", "projects", "activities", "additional"]}

PROMPT = """You convert a resume into the Harvard resume format. Return JSON only.

THE ONE RULE: use only facts that are in the resume. Never add an employer,
title, date, number, percentage, location, tool, skill, certification or
achievement that the resume does not state. If something is missing, leave
the field as an empty string. Never guess it and never write a placeholder.
Every value you output will be checked against the source text, and invented
values will be deleted.

Fields:
- name, location, phone, email: copied exactly. links: URLs without "https://"
  or "www.". Include a link only if the resume shows it.
- education: newest first. dates such as "2015 to 2019" or "Graduated 2018".
  details: honours, grades, GPA or relevant coursework, only if the resume
  states them. Never an address.
- experience: paid roles, newest first. org is the employer name. title is the
  job title. location is only what the resume says, e.g. "Remote" or
  "Manila, Philippines". dates look like "Jun 2023 to Present", using the
  resume's own months and years. Write ranges with " to ", not a dash.
- bullets: rewrite each duty or result as one concise line (at most about 110
  characters) that starts with a strong past-tense action verb. Use present
  tense only when the role's end date is literally "Present" or "Current",
  and then keep every verb in that bullet in the present. A role with an end
  month and year is past tense, even a recent one. Keep each bullet's substance
  and any numbers exactly as given. Merge duplicates. Drop filler such as "with
  exceptional attention to detail" or "in fast-paced environments". Keep every
  distinct responsibility, tool and result. Use at most 10 bullets per role,
  most important first, and merge before you drop anything. Name the tools
  in the bullet where the resume ties them to that work.
- freelance or contract work for several clients is ONE experience entry:
  org "Freelance" (or the resume's business name), the resume's own title,
  dates from the earliest listed start to the latest listed end, and one
  bullet per client that names the client and the work ("Designed a brand
  identity package for Lumina Cafe"). Merge similar client work into one
  bullet. Do not repeat the dates inside a bullet.
- projects: personal, academic or portfolio builds only, never client work.
  stack is a comma-separated list of the project's technologies. dates only
  if the resume gives them.
- activities: volunteering, leadership, organisations or freelance side work
  the resume lists, in the same shape as experience. Leave it empty if there
  are none.
- additional: grouped lines, in this order when present: "Technical Skills",
  a group per other professional skill area the resume lists (for example
  "Administrative Skills" or "Design Skills", named after the resume's own
  heading), then "Tools", "Certifications & Training", "Languages",
  "Interests". items are short entries copied from the resume. Merge near
  duplicates such as "Storage Administration" and "Storage & Backup
  Administration". Keep every job skill, including ones like data entry,
  calendar management, customer service, scheduling, proofreading and
  stakeholder management, because employers search for them. Leave out only
  personality traits ("detail-oriented", "fast learner", "strong
  communication", "proactive mindset"). Keep a certification's grade, year
  and issuer when the resume gives them. A language is one item with its
  level in brackets, e.g. "English (professional working proficiency)".
- Leave out any summary, objective or "professional strengths" section. Move
  any concrete fact from those sections that appears nowhere else (a tool, a
  certification, a language) into the matching field.
"""


def ask_model(text, feedback=""):
    body = {
        "systemInstruction": {"parts": [{"text": PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text":
            "RESUME TEXT:\n<<<\n" + text + "\n>>>" + feedback}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json",
                             "responseSchema": SCHEMA},
    }
    failed = []
    for model in MODELS:
        req = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % model,
            data=json.dumps(body).encode(),
            headers={"x-goog-api-key": api_key(), "content-type": "application/json",
                     "user-agent": "TheJobStash-harvard/1.0"})
        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=90) as r:
                    doc = json.load(r)
                USED.append(model)
                return json.loads(doc["candidates"][0]["content"]["parts"][0]["text"])
            except urllib.error.HTTPError as ex:
                # 429 is a quota on this model: waiting will not fix it, the
                # next model has its own. 500/503 is "busy" and clears in seconds.
                if ex.code not in (429, 500, 503):
                    raise
                if ex.code != 429 and attempt == 0:
                    time.sleep(5)
                    continue
                failed.append("%s: HTTP %s" % (model, ex.code))
                break
            except (TimeoutError, urllib.error.URLError) as ex:
                # A model that has not answered in 90s is overloaded. Asking
                # it again doubles the wait, so move on to the next one.
                failed.append("%s: %s" % (model, type(ex).__name__))
                break
    raise RuntimeError("Gemini could not take the request (%s)" % "; ".join(failed))
    raise last


# ---------------------------------------------------------------------------
# holding the model to the source
# ---------------------------------------------------------------------------

def _in(value, src_norm):
    return not norm(value) or norm(value) in src_norm


def _words_in(value, src_words):
    """Every word of 3+ letters appears somewhere in the source. Used for
    titles and orgs, which the model may reorder ('Analyst II, Infrastructure')."""
    return all(w in src_words for w in re.findall(r"[a-z0-9]{3,}", value.lower()))


def check_facts(d, src):
    """Every value the reader would take as a fact, which the source does not support."""
    src_norm = norm(src)
    src_words = set(re.findall(r"[a-z0-9]{3,}", src.lower()))
    src_nums = set(re.findall(r"\d+", src))
    bad = []

    def nums(where, s):
        for n in re.findall(r"\d+", s or ""):
            if n not in src_nums:
                bad.append((where, s, "number %s is not in the resume" % n))

    for k in ("name", "phone", "email"):
        if not _in(d.get(k, ""), src_norm):
            bad.append((k, d[k], "not in the resume"))
    if d.get("location") and not _words_in(d["location"], src_words):
        bad.append(("location", d["location"], "not in the resume"))
    for l in d.get("links", []):
        if not _in(l, src_norm):
            bad.append(("links", l, "not in the resume"))
    for e in d.get("education", []):
        for k in ("school", "degree", "location"):
            if not _words_in(e.get(k, ""), src_words):
                bad.append(("education." + k, e[k], "not in the resume"))
        nums("education.dates", e.get("dates"))
        for x in e.get("details", []):
            nums("education.details", x)
    for sec in ("experience", "activities"):
        for e in d.get(sec, []):
            for k in ("org", "title", "location"):
                if not _words_in(e.get(k, ""), src_words):
                    bad.append((sec + "." + k, e[k], "not in the resume"))
            nums(sec + ".dates", e.get("dates"))
            for b in e.get("bullets", []):
                nums(sec + ".bullets", b)
    for p in d.get("projects", []):
        if not _words_in(p.get("name", ""), src_words):
            bad.append(("projects.name", p["name"], "not in the resume"))
        for s in re.split(r",\s*", p.get("stack", "")):
            if not _in(s, src_norm):
                bad.append(("projects.stack", s, "not in the resume"))
        for b in p.get("bullets", []):
            nums("projects.bullets", b)
        nums("projects.dates", p.get("dates"))
    for g in d.get("additional", []):
        for it in g.get("items", []):
            # "Microsoft Office Suite (Excel, Word)" is fine if each part is.
            parts = [x for x in re.split(r"[(),;/]", it) if x.strip()]
            if not all(_words_in(x, src_words) for x in parts):
                bad.append(("additional." + g.get("label", ""), it, "not in the resume"))
    return bad


def strip_facts(d, bad):
    """Last resort after the retry: remove what still is not in the source."""
    kill = {(w, v) for w, v, _ in bad}
    for g in d.get("additional", []):
        g["items"] = [i for i in g["items"]
                      if ("additional." + g["label"], i) not in kill]
    d["additional"] = [g for g in d.get("additional", []) if g["items"]]
    for sec in ("experience", "activities"):
        for e in d.get(sec, []):
            e["bullets"] = [b for b in e["bullets"] if (sec + ".bullets", b) not in kill]
            for k in ("location", "dates"):
                if (sec + "." + k, e[k]) in kill:
                    e[k] = ""
    for p in d.get("projects", []):
        p["bullets"] = [b for b in p["bullets"] if ("projects.bullets", b) not in kill]
        p["stack"] = ", ".join(s for s in re.split(r",\s*", p["stack"])
                               if ("projects.stack", s) not in kill)
    d["links"] = [l for l in d.get("links", []) if ("links", l) not in kill]
    return d


def lost_skills(d, text):
    """Skills the scorer finds in the source but not in the conversion. A
    Harvard page that drops them reads cleaner and matches fewer jobs."""
    return sorted(set(R.find_skills(text)) - set(R.find_skills(page_text(to_html(d)))))


def convert(text):
    d = ask_model(text)
    bad, lost = check_facts(d, text), lost_skills(d, text)
    retried = False
    if bad or lost:
        retried = True
        note = ""
        if bad:
            note += ("\n\nYour previous answer contained values that are NOT in "
                     "the resume. Leave them out:\n" +
                     "\n".join("- %s: %r (%s)" % b for b in bad))
        if lost:
            note += ("\n\nYour previous answer dropped these skills, which the "
                     "resume does list. Keep each one, in a bullet or in "
                     "additional: " + ", ".join(lost))
        d = ask_model(text, note)
        bad = check_facts(d, text)
        d = strip_facts(d, bad)
        lost = lost_skills(d, text)
    if lost:
        d = add_back(d, text, lost)
        lost = lost_skills(d, text)
    return fix_tense(d), bad, lost, retried


NOT_SKILLS = ("tool", "certif", "language", "interest")

# ponytail: a fixed verb list, not a grammar. A verb missing from it is left
# alone, which is the safe failure. Extend it when a real resume shows one.
PAST = {v: v + "d" for v in (
    "analyze", "automate", "collaborate", "compile", "coordinate", "create",
    "curate", "design", "document", "enhance", "ensure", "execute",
    "facilitate", "generate", "guide", "handle", "improve", "integrate",
    "leverage", "manage", "migrate", "operate", "optimize", "organize",
    "prepare", "produce", "reduce", "resolve", "schedule", "serve",
    "standardize", "streamline", "supervise", "translate", "update",
    "validate", "contribute")}
PAST.update({v: v + "ed" for v in (
    "answer", "assist", "audit", "collect", "conduct", "consult", "convert",
    "deliver", "deploy", "develop", "direct", "draft", "edit", "engineer",
    "establish", "expand", "implement", "install", "launch", "maintain",
    "mentor", "monitor", "own", "partner", "perform", "present", "process",
    "record", "refactor", "report", "research", "respond", "review",
    "support", "test", "track", "train", "work")})
PAST.update({"build": "built", "lead": "led", "run": "ran", "make": "made",
             "write": "wrote", "teach": "taught", "oversee": "oversaw",
             "drive": "drove", "grow": "grew", "sell": "sold", "hold": "held",
             "keep": "kept", "bring": "brought", "take": "took", "give": "gave",
             "ship": "shipped", "plan": "planned", "troubleshoot": "troubleshot",
             "carry": "carried", "apply": "applied", "identify": "identified",
             "verify": "verified", "modify": "modified", "copy": "copied"})
CURRENT = re.compile(r"\b(present|current|now)\b", re.I)


def fix_tense(d):
    """A finished role reads in the past tense. Models, the lite ones most of
    all, copy a present-tense bullet or treat a recent end date as current."""
    for x in d.get("experience", []) + d.get("activities", []):
        if CURRENT.search(x["dates"]) or not x["dates"]:
            continue
        for i, b in enumerate(x["bullets"]):
            first, _, rest = b.partition(" ")
            past = PAST.get(first.lower())
            if past:
                x["bullets"][i] = past.capitalize() + " " + rest
                # "Build and maintain X" -> "Built and maintained X"
                m = re.match(r"(\w+ and )(\w+)(.*)", x["bullets"][i])
                if m and m.group(2).lower() in PAST:
                    x["bullets"][i] = m.group(1) + PAST[m.group(2).lower()] + m.group(3)
    return d


def add_back(d, text, lost):
    """Still dropped after the retry: put each skill back in the resume's own
    words. Safe, because each one was found in the source text."""
    words = []
    for s in lost:
        m = re.search(r"(?<![a-z0-9])%s(?![a-z0-9])" % re.escape(s), text, re.I)
        w = m.group(0) if m else s
        words.append(w[:1].upper() + w[1:] if w.islower() else w)
    groups = [g for g in d.setdefault("additional", [])
              if not any(x in g["label"].lower() for x in NOT_SKILLS)]
    if groups:
        groups[-1]["items"] += words
    else:
        d["additional"].insert(0, {"label": "Skills", "items": words})
    return d


# ---------------------------------------------------------------------------
# rendering (CSS from JobHunt/resume/build_resume.py, which prints Justin's)
# ---------------------------------------------------------------------------

CSS = """
@page { size: A4; margin: 13mm 14mm; }
body { font-family: Arial, Helvetica, sans-serif; font-size: 10.3pt; line-height: 1.28;
       color: #000; margin: 0; }
h1 { font-size: 15pt; letter-spacing: .5px; text-align: center; margin: 0 0 3px;
     text-transform: uppercase; }
.contact { text-align: center; font-size: 9.6pt; margin: 0 0 2px; }
h2 { font-size: 10.3pt; letter-spacing: .6px; border-bottom: 1px solid #000;
     margin: 11px 0 5px; padding-bottom: 1px; }
.entry { break-inside: avoid; }
.row { display: flex; justify-content: space-between; align-items: baseline; }
.org { font-weight: bold; text-transform: uppercase; }
.loc { font-style: italic; font-size: 9.6pt; white-space: nowrap; padding-left: 10px; }
.title { font-style: italic; }
.dates { font-style: italic; font-size: 9.6pt; white-space: nowrap; padding-left: 10px; }
ul { margin: 2px 0 6px; padding-left: 15px; }
li { margin-bottom: 1.5px; }
.stack { font-size: 9.6pt; font-style: italic; }
.skills p { margin: 0 0 2.5px; }
"""

e = lambda s: html.escape(s or "")


def _row(left, lcls, right, rcls):
    return ("<div class='row'><span class='%s'>%s</span><span class='%s'>%s</span></div>"
            % (lcls, e(left), rcls, e(right)))


def _ul(items):
    return "<ul>" + "".join("<li>%s</li>" % e(b) for b in items) + "</ul>" if items else ""


def _entries(title, items):
    if not items:
        return []
    out = ["<h2>%s</h2>" % title]
    for x in items:
        out.append("<div class='entry'>" + _row(x["org"], "org", x["location"], "loc") +
                   _row(x["title"], "title", x["dates"], "dates") + _ul(x["bullets"]) + "</div>")
    return out


def page_text(page):
    """Plain text of a rendered page, the way the scorer would read it."""
    return html.unescape(re.sub(r"<[^>]+>", "\n", page.split("</style>", 1)[1]))


def to_html(d):
    contact = [x for x in (d.get("location"), d.get("phone") and "P: " + d["phone"],
                           d.get("email")) if x]
    out = ["<!doctype html><html><head><meta charset='utf-8'><title>%s</title>"
           "<style>%s</style></head><body>" % (e(d["name"]), CSS),
           "<h1>%s</h1>" % e(d["name"]),
           "<p class='contact'>%s</p>" % e(" | ".join(contact))]
    if d.get("links"):
        out.append("<p class='contact'>%s</p>" % e(" | ".join(d["links"])))
    if d.get("education"):
        out.append("<h2>EDUCATION</h2>")
        for x in d["education"]:
            out.append("<div class='entry'>" + _row(x["school"], "org", x["location"], "loc") +
                       _row(x["degree"], "title", x["dates"], "dates") +
                       _ul(x.get("details")) + "</div>")
    out += _entries("WORK EXPERIENCE", d.get("experience"))
    if d.get("projects"):
        out.append("<h2>PROJECTS</h2>")
        for p in d["projects"]:
            second = (_row(p["stack"], "stack", p.get("dates", ""), "dates")
                      if p["stack"] or p.get("dates") else "")
            out.append("<div class='entry'>" + _row(p["name"], "org", p["link"], "loc") + second +
                       _ul(p["bullets"]) + "</div>")
    out += _entries("LEADERSHIP & ACTIVITIES", d.get("activities"))
    if d.get("additional"):
        out.append("<h2>ADDITIONAL</h2><div class='skills'>")
        for g in d["additional"]:
            out.append("<p><b>%s:</b> %s</p>" % (e(g["label"]), e(", ".join(g["items"]))))
        out.append("</div>")
    out.append("</body></html>")
    return "\n".join(out)


# ---------------------------------------------------------------------------

def profile_view(text):
    """What the scorer makes of a resume, for the before/after in the result."""
    _, diag = R.parse_profile(text)
    return {k: diag[k] for k in ("families", "years", "level", "skills_found", "top_skills")}


def warnings_for(d):
    w = []
    for x in d.get("experience", []) + d.get("activities", []):
        if not x["dates"]:
            w.append("No dates for %s at %s. Add them: the Harvard format "
                     "and the job scorer both need them." % (x["title"], x["org"]))
    if not d.get("education"):
        w.append("No education section found.")
    if not d.get("experience"):
        w.append("No work experience found.")
    return w


def run(src_path, out_base):
    text = read_text(src_path)
    d, bad, lost, retried = convert(text)
    page = to_html(d)
    html_path = os.path.abspath(out_base + ".html")
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(page)
    with open(out_base + ".json", "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)
    pdf = render._print_pdf(html_path, os.path.abspath(out_base + ".pdf"))
    return {
        "ok": bool(pdf), "pdf": pdf, "html": html_path, "model": ", ".join(dict.fromkeys(USED)),
        "warnings": warnings_for(d), "retried": retried,
        "removed_unsupported": ["%s: %s" % (w, v) for w, v, _ in bad],
        "skills_dropped": lost,
        "scorer_before": profile_view(text),
        "scorer_after": profile_view(page_text(page)),
        "error": None if pdf else "Chrome could not print the PDF",
    }


KEEP_SECONDS = 3600


def sweep():
    """Delete conversions older than an hour. The workflow has already sent
    them back by then, and they are personal data."""
    now = time.time()
    for f in os.listdir(DIR):
        p = os.path.join(DIR, f)
        if os.path.isfile(p) and now - os.path.getmtime(p) > KEEP_SECONDS:
            os.remove(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?")
    ap.add_argument("outdir", nargs="?")
    ap.add_argument("--id")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    try:
        if a.id is not None:
            if not ID_RE.match(a.id):
                raise ValueError("bad id")
            src = next((os.path.join(DIR, a.id + x) for x in (".pdf", ".docx", ".txt")
                        if os.path.exists(os.path.join(DIR, a.id + x))), None)
            if not src:
                raise ValueError("no upload for id %s" % a.id)
            sweep()
            try:
                res = run(src, os.path.join(DIR, a.id + "-harvard"))
            finally:
                os.remove(src)          # the upload is someone's resume
        elif a.src:
            outdir = a.outdir or DIR
            os.makedirs(outdir, exist_ok=True)
            base = os.path.splitext(os.path.basename(a.src))[0] + "-harvard"
            res = run(a.src, os.path.join(outdir, base))
        else:
            ap.error("give a file or --id")
        res["id"] = a.id
    except Exception as ex:
        res = {"ok": False, "id": a.id, "error": "%s: %s" % (type(ex).__name__, ex)}
    print(json.dumps(res, ensure_ascii=False, indent=None if a.json else 1))
    # Under --json the document is the verdict. A non-zero exit makes n8n drop
    # stdout, and the caller would lose the reason.
    return 0 if res["ok"] or a.json else 1


if __name__ == "__main__":
    sys.exit(main())
