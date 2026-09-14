# -*- coding: utf-8 -*-
"""
Resume file -> a profiles.Profile.

Deterministic on purpose. An LLM would read a resume better, but this runs with
no API key, no per-upload cost and no network call, and it is auditable - when
a user says "it missed my Django experience" there is a rule to point at. The
LLM upgrade slots in at parse_profile(); everything downstream takes a Profile
and does not care where it came from.

Reads .pdf (pypdf), .docx (python-docx), .txt and .md.

What it pulls out:
  skills          matched against SKILL_VOCAB, weighted by where they appear
  years           from employment date ranges, not from prose
  level           from the most senior job title held
  role families   from the titles held, mapped to the catalogue below
  country         from location tokens
"""
import io, os, re, sys, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from profiles import (Profile, TECH_VOCAB, COUNTRY_TOKENS, LEVEL_RANK,
                      COUNTRY_AUTH)

# ---------------------------------------------------------------------------
# Professions. JobHunt only knows about developers, which is why 2,110 of its
# 3,730 scraped rows were thrown away as "not a role family you work in" - they
# were nurses, accountants and VAs. A product cannot do that, so each family
# carries both the title patterns that identify it and the skills that belong
# to it.
# ---------------------------------------------------------------------------
ROLE_CATALOGUE = {
    "software": {
        # These must stay job-title shaped, like every other family's. Bare
        # common nouns here read as "this person is a developer" off ordinary
        # prose: "consistent application of guidelines", "professional
        # development", "Mobile: 0976...". One title hit scores 3, which is
        # exactly the inclusion threshold in find_families(), so a single
        # stray word was enough to put a teacher on a software profile and
        # send them IT jobs. Same class of bug as the summariser splitting
        # "Adobe Experience Manager" - see HANDOFF.md section 5.
        "titles": [r"\bdeveloper\b",
                   r"\b(software|web|application|product|game) development\b",
                   r"\bengineer(ing)?\b",
                   r"\bprogrammer\b", r"\bfull.?stack\b", r"\bfront.?end\b",
                   r"\bback.?end\b", r"\bsoftware\b",
                   r"\bweb (developer|designer|engineer|programmer)\b",
                   r"\bapplications? (developer|engineer|programmer)\b",
                   r"\bmobile (developer|engineer|app|application)\b"],
        "skills": ["react", "next.js", "vue", "angular", "svelte", "typescript",
                   "javascript", "node", "express", "php", "laravel", "python",
                   "django", "flask", "java", "spring", "c#", ".net", "ruby",
                   "rails", "golang", "rust", "swift", "kotlin", "flutter",
                   "react native", "html", "css", "tailwind",
                   "wordpress", "elementor", "woocommerce", "shopify", "wix",
                   "webflow", "jquery", "bootstrap", "sass", "graphql",
                   "rest api", "postgres", "postgresql", "mysql", "mongodb",
                   "redis", "docker", "git", "aws", "azure", "gcp"],
    },
    "data": {
        "titles": [r"\bdata (analyst|engineer|scientist)\b", r"\banalytics\b",
                   r"\bbusiness intelligence\b", r"\breporting\b",
                   r"\bmachine learning\b", r"\bml engineer\b"],
        "skills": ["sql", "python", "pandas", "numpy", "power bi", "tableau",
                   "looker", "qlik", "bigquery", "snowflake", "databricks",
                   "airflow", "spark", "hadoop", "dbt", "excel", "r",
                   "machine learning", "pytorch", "tensorflow"],
    },
    "design": {
        "titles": [r"\b(ui|ux)\b", r"\bdesigner\b", r"\bgraphic (artist|designer)\b",
                   r"\bproduct designer\b", r"\bcreative\b", r"\bbrand\b"],
        "skills": ["figma", "sketch", "adobe xd", "photoshop", "illustrator",
                   "indesign", "after effects", "prototyping", "wireframing",
                   "design systems", "user research", "canva", "webflow"],
    },
    "qa": {
        "titles": [r"\bqa\b", r"\bquality assurance\b", r"\btest(er|ing)\b",
                   r"\bsdet\b", r"\bautomation engineer\b"],
        "skills": ["selenium", "cypress", "playwright", "jest", "pytest",
                   "postman", "jira", "test automation", "manual testing",
                   "regression testing", "api testing"],
    },
    "devops": {
        "titles": [r"\bdevops\b", r"\bsre\b", r"\bsite reliability\b",
                   r"\bplatform engineer\b", r"\binfrastructure\b",
                   r"\bcloud engineer\b", r"\bsysadmin\b",
                   r"\bsystems administrator\b"],
        "skills": ["kubernetes", "docker", "terraform", "ansible", "jenkins",
                   "github actions", "aws", "azure", "gcp", "linux", "bash",
                   "prometheus", "grafana", "ci/cd", "openshift"],
    },
    "product": {
        "titles": [r"\bproduct (manager|owner)\b", r"\bscrum master\b",
                   r"\bbusiness analyst\b", r"\bproject manager\b",
                   r"\bprogram manager\b"],
        "skills": ["jira", "confluence", "roadmap", "agile", "scrum", "kanban",
                   "stakeholder management", "user stories", "backlog",
                   "product strategy", "a/b testing", "analytics"],
    },
    "marketing": {
        "titles": [r"\bmarketing\b", r"\bseo\b", r"\bcontent (writer|manager|strategist)\b",
                   r"\bsocial media\b", r"\bcopywriter\b", r"\bgrowth\b",
                   r"\bbrand manager\b"],
        "skills": ["seo", "sem", "google ads", "google analytics", "hubspot",
                   "mailchimp", "content marketing", "copywriting",
                   "social media", "meta ads", "email marketing", "canva",
                   "wordpress", "klaviyo"],
    },
    "sales": {
        "titles": [r"\bsales\b", r"\baccount (executive|manager)\b",
                   r"\bbusiness development\b", r"\bsdr\b", r"\bbdr\b",
                   r"\bpartnerships\b"],
        "skills": ["salesforce", "hubspot", "outreach", "cold calling",
                   "lead generation", "crm", "pipeline management",
                   "negotiation", "account management"],
    },
    "support": {
        "titles": [r"\b(customer|technical) (support|success|service)\b",
                   r"\bhelp ?desk\b", r"\bsupport (engineer|specialist|agent)\b"],
        "skills": ["zendesk", "intercom", "freshdesk", "jira service desk",
                   "troubleshooting", "ticketing", "customer service", "crm",
                   "sla"],
    },
    "finance": {
        "titles": [r"\baccountant\b", r"\baccounting\b", r"\bbookkeep(er|ing)\b",
                   r"\bfinancial analyst\b", r"\bpayroll\b", r"\baudit(or)?\b",
                   r"\bcontroller\b"],
        "skills": ["quickbooks", "xero", "sap", "excel", "netsuite",
                   "reconciliation", "accounts payable", "accounts receivable",
                   "financial reporting", "gaap", "payroll", "taxation"],
    },
    "admin": {
        # Audited 2026-09-12 against a real clerical resume. Three faults, all
        # visible only by reading the excluded pile:
        #
        #  too narrow  "Legal File Clerk" and "Video Annotator" were excluded
        #              outright - the second is literally what that resume asks
        #              for - because no pattern here covered clerk, encoder,
        #              annotator or transcriptionist.
        #  too rigid   "Administrative & Bookkeeping Assistant" failed because
        #              the old pattern needed the two words adjacent.
        #  too loose   bare \boperations\b pulled in "Security Operations
        #              Center", "Campaign Operations" and "Marketing
        #              Operations" - different professions entirely. Same fault
        #              as bare \bapplication\b in the software family.
        "titles": [r"\bvirtual assistant\b", r"\bexecutive assistant\b",
                   r"\badmin(istrative)?\b[\w&, /-]{0,24}\b"
                   r"(assistant|officer|clerk|support|staff)\b",
                   r"\bdata entry\b", r"\bdata encoder\b", r"\bencoder\b",
                   r"\b(file|records?|office|clerical|billing) clerk\b",
                   r"\bclerical\b", r"\bback.?office\b",
                   r"\b(data )?annotat(or|ion)\b",
                   r"\btranscription(ist)?\b",
                   r"\bdata processing\b", r"\brecords (officer|management)\b",
                   r"\boffice (assistant|administrator)\b",
                   r"\b(office|business|admin(istrative)?) operations\b",
                   r"\boperations (assistant|associate|clerk)\b",
                   # Bare coordinator pulled "HR Coordinator", "Sales
                   # Operations Coordinator" and "Sales Management
                   # Coordinator" into a clerical profile - other
                   # professions entirely. They then rendered under "Came
                   # close" with "Centres on work outside your field"
                   # printed beside them. Same fault as bare operations.
                   r"\b(office|admin(istrative)?|data|records?|billing|"
                   r"scheduling|clerical|executive) coordinator\b"],
        "skills": ["excel", "google workspace", "google sheets", "google docs",
                   "google forms", "calendar management",
                   "data entry", "data annotation", "transcription",
                   "recordkeeping", "record keeping", "data organization",
                   "scheduling", "travel arrangements", "filing",
                   "microsoft office", "microsoft word", "spreadsheets",
                   "notion", "asana", "trello", "slack"],
    },
    "hr": {
        "titles": [r"\brecruit(er|ment)\b", r"\bhuman resources\b", r"\bhr\b",
                   r"\btalent acquisition\b", r"\bpeople operations\b"],
        "skills": ["ats", "greenhouse", "lever", "workday", "onboarding",
                   "sourcing", "interviewing", "employee relations",
                   "performance management", "linkedin recruiter"],
    },
    "healthcare": {
        "titles": [r"\bnurse\b", r"\bnursing\b", r"\bmedical\b",
                   r"\bcaregiver\b", r"\bphysician\b", r"\btherapist\b",
                   r"\bpharmac(y|ist)\b"],
        "skills": ["patient care", "bls", "acls", "emr", "hipaa",
                   "medication administration", "vital signs", "triage",
                   "clinical documentation"],
    },
    "writing": {
        "titles": [r"\b(technical )?writer\b", r"\beditor\b",
                   r"\bcontent creator\b", r"\bjournalist\b",
                   r"\bproofread(er|ing)\b"],
        "skills": ["copywriting", "technical writing", "editing", "seo",
                   "wordpress", "markdown", "content strategy", "proofreading",
                   "ap style"],
    },
}

# Everything the parser can recognise, deduped across families plus the tech
# vocabulary the matcher already knows.
SKILL_VOCAB = sorted({s for fam in ROLE_CATALOGUE.values() for s in fam["skills"]}
                     | set(TECH_VOCAB))

# A "Skills" heading, so terms listed there can outweigh a passing mention.
_SKILL_SECTION = re.compile(
    r"(?:^|\n)\s*(technical skills|core competencies|skills(?:\s*&\s*tools)?|"
    r"technologies|tech stack|competencies|expertise)\s*:?\s*\n",
    re.I)

_LEVEL_WORDS = [
    ("exec",      r"\b(chief|cto|cio|ceo|vp|vice president|head of|director)\b"),
    ("principal", r"\b(principal|distinguished|staff engineer|architect)\b"),
    ("lead",      r"\b(team lead|tech lead|technical lead|lead engineer|"
                  r"lead developer|engineering manager|supervisor)\b"),
    # "Senior High School" is a school year in several countries, including the
    # Philippines, and reading it as a job title promotes people two levels.
    ("senior",    r"\b(senior(?!\s+high)|sr\.)\b"),
    ("junior",    r"\b(junior(?!\s+high)|jr\.|entry.level|intern|trainee)\b"),
]

# Resume section headings. A date range means completely different things in
# each: under EXPERIENCE it is a job, under EDUCATION it is a course, and
# counting the second as the first is how a bootcamp becomes a year of work.
_SECTION_HEADS = [
    ("education",  r"\b(education|academic|qualifications|certifications?|"
                   r"training|courses?|licences?|licenses?)\b"),
    ("experience", r"\b(experience|employment|work history|professional|"
                   r"career|positions? held)\b"),
    ("skills",     r"\b(technical skills|skills|technologies|tech stack|"
                   r"competencies|expertise)\b"),
]

# Words that mark a date range as study rather than work, wherever it appears.
_STUDY_CONTEXT = re.compile(
    r"\b(bootcamp|boot camp|bachelor|master|mba|degree|diploma|university|"
    r"academy|certificat\w+|course|curriculum|gpa|final grade|graduated|"
    r"undergraduate|postgraduate|senior high|junior high|high school)\b", re.I)

# "Jun 2023 - Sep 2026", "2018 to present", "03/2020 - 05/2022"
_MONTHS = ("jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec")
_RANGE = re.compile(
    r"(?:(%s)\w*\s+)?(\d{4})\s*(?:-|–|—|to|until)\s*"
    r"(?:(%s)\w*\s+)?(\d{4}|present|current|now)" % (_MONTHS, _MONTHS), re.I)


# ---------------------------------------------------------------------------
# text extraction
# ---------------------------------------------------------------------------

def extract_text(path_or_bytes, filename=""):
    """Pull plain text out of a resume file. Returns "" on anything unreadable."""
    name = (filename or str(path_or_bytes)).lower()
    if isinstance(path_or_bytes, (bytes, bytearray)):
        blob, path = bytes(path_or_bytes), None
    else:
        path, blob = path_or_bytes, None

    try:
        if name.endswith(".pdf"):
            import pypdf
            src = io.BytesIO(blob) if blob is not None else path
            reader = pypdf.PdfReader(src)
            return "\n".join((p.extract_text() or "") for p in reader.pages)
        if name.endswith(".docx"):
            import docx
            src = io.BytesIO(blob) if blob is not None else path
            d = docx.Document(src)
            parts = [p.text for p in d.paragraphs]
            for t in d.tables:                       # skills often live in tables
                for row in t.rows:
                    parts += [c.text for c in row.cells]
            return "\n".join(parts)
        if blob is not None:
            return blob.decode("utf-8", errors="replace")
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except Exception as e:
        return "__PARSE_ERROR__ %s: %s" % (type(e).__name__, e)


# ---------------------------------------------------------------------------
# field extraction
# ---------------------------------------------------------------------------

def _tok(needle, hay):
    return re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])",
                     hay) is not None


def find_skills(text):
    """skill -> weight. Weight reflects how hard the resume argues for it.

    A term inside a Skills section is a claim; the same term buried once in a
    paragraph is a mention. Treating those identically is how a matcher ends up
    confident about a technology somebody used once.
    """
    low = text.lower()
    section = ""
    m = _SKILL_SECTION.search(low)
    if m:
        section = low[m.end(): m.end() + 1200]

    out = {}
    for skill in SKILL_VOCAB:
        if not _tok(skill, low):
            continue
        count = len(re.findall(r"(?<![a-z0-9])" + re.escape(skill) +
                               r"(?![a-z0-9])", low))
        weight = 3
        if section and _tok(skill, section):
            weight += 2                    # explicitly claimed
        if count >= 3:
            weight += 1                    # recurs across roles
        out[skill] = min(weight, 6)
    return out


def _section_at(text, pos):
    """Which resume section a character offset falls in.

    Scans backwards for the nearest heading rather than parsing the document
    structure, because resumes have no structure worth parsing.
    """
    best_name, best_pos = None, -1
    head = text[:pos]
    for name, pattern in _SECTION_HEADS:
        for m in re.finditer(pattern, head, re.I):
            # A heading sits on a short line of its own; the same word inside a
            # sentence is not one.
            line_start = head.rfind("\n", 0, m.start()) + 1
            line_end = head.find("\n", m.end())
            line = head[line_start: line_end if line_end != -1 else len(head)]
            if len(line.strip()) <= 40 and m.start() > best_pos:
                best_name, best_pos = name, m.start()
    return best_name


def _merge_years(spans):
    if not spans:
        return None
    spans = sorted(spans)
    merged = [list(spans[0])]
    for s, e in spans[1:]:
        if s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return sum(e - s for s, e in merged) or 1


def find_years(text, families=None):
    """Years of employment, from date ranges rather than prose.

    Returns (relevant_years, total_years). Two numbers because they answer
    different questions: somebody who spent four years as a graphic artist and
    three as a developer has seven years of work and three years that a
    software employer will count. Scoring seniority off the larger number
    pushes them into roles that will reject them on experience.

    Study ranges are excluded outright. Overlapping employment is merged, so a
    contract running alongside a full-time role is not counted twice.
    """
    this_year = datetime.date.today().year
    family_patterns = []
    for fam in (families or []):
        family_patterns += ROLE_CATALOGUE.get(fam, {}).get("titles", [])

    all_spans, rel_spans = [], []
    for m in _RANGE.finditer(text):
        try:
            start = int(m.group(2))
        except (TypeError, ValueError):
            continue
        end_raw = (m.group(4) or "").lower()
        if end_raw in ("present", "current", "now"):
            end = this_year
        else:
            try:
                end = int(end_raw)
            except ValueError:
                continue
        if not (1970 <= start <= this_year and start <= end <= this_year + 1):
            continue

        # The employer and title sit on the line holding the dates and the one
        # above it. A wider character window bleeds across entries - a fixed
        # 160-char lookback reached back into the education section and tagged
        # the main job as study, deleting the only experience that counted.
        head = text[:m.start()]
        context = " ".join(head.split("\n")[-2:])[-140:]

        if _STUDY_CONTEXT.search(context) or _section_at(text, m.start()) == "education":
            continue

        span = (start, min(end, this_year))
        all_spans.append(span)
        if not family_patterns or any(re.search(p, context, re.I)
                                      for p in family_patterns):
            rel_spans.append(span)

    total = _merge_years(all_spans)
    relevant = _merge_years(rel_spans)
    return relevant, total


def find_level(text, years):
    """Most senior title the resume claims, falling back to the years figure."""
    low = text.lower()
    for level, pattern in _LEVEL_WORDS:
        if re.search(pattern, low):
            return level
    if years is None:
        return "mid"
    if years <= 1:
        return "junior"
    if years <= 4:
        return "mid"
    if years <= 7:
        return "senior"
    return "lead"


def find_families(text, skills):
    """Which professions this resume is for.

    Scored on titles first because a title is a claim about what somebody was
    hired to do; skills only break ties, since "excel" appears on almost every
    resume ever written.
    """
    low = text.lower()
    scores = {}
    for fam, spec in ROLE_CATALOGUE.items():
        title_hits = sum(1 for p in spec["titles"] if re.search(p, low))
        skill_hits = sum(1 for s in spec["skills"] if s in skills)
        score = title_hits * 3 + skill_hits
        if title_hits or skill_hits >= 3:
            scores[fam] = score
    if not scores:
        return ["software"], {}
    best = max(scores.values())
    picked = [f for f, s in scores.items() if s >= max(best * 0.5, 3)]
    return sorted(picked, key=lambda f: -scores[f])[:3], scores


def find_country(text):
    low = text.lower()
    best, best_hits = None, 0
    for country, tokens in COUNTRY_TOKENS.items():
        hits = sum(1 for t in tokens if t in low)
        if hits > best_hits:
            best, best_hits = country, hits
    return best or "philippines"


def find_email(text):
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text or "")
    return m.group(0) if m else None


# ---------------------------------------------------------------------------
# the whole thing
# ---------------------------------------------------------------------------

def parse_profile(text, user_id="anonymous", overrides=None):
    """Resume text -> (Profile, diagnostics dict shown back to the user)."""
    overrides = overrides or {}
    skills = find_skills(text)
    # Order matters: families decide which employment counts as relevant, and
    # relevant years decide the level.
    families, family_scores = find_families(text, skills)
    years, total_years = find_years(text, families)
    if years is None:
        years = total_years
    level = find_level(text, years)
    country = find_country(text)

    patterns, fam_skills = [], set()
    for fam in families:
        patterns += ROLE_CATALOGUE[fam]["titles"]
        fam_skills |= set(ROLE_CATALOGUE[fam]["skills"])

    # Three overlapping skills is the right bar for a rich resume and far too
    # high for a sparse one, where it would block everything.
    min_hits = 3 if len(skills) >= 8 else (2 if len(skills) >= 4 else 1)

    profile = Profile(
        user_id=user_id,
        role_families=sorted(set(patterns)),
        family_skills=sorted(fam_skills),
        strong_skills=skills,
        adjacent_hints=[],
        min_skill_hits=overrides.get("min_skill_hits", min_hits),
        # None, not 0. "Cannot determine" is not "fresh out of school": the
        # 0 gated an 11-year professional out of every posting asking for
        # experience at all.
        years_experience=overrides.get("years_experience", years),
        level=overrides.get("level", level),
        home_country=overrides.get("home_country", country),
        authorized_in=overrides.get(
            "authorized_in", [COUNTRY_AUTH.get(
                overrides.get("home_country", country), "ph")]),
        sponsorship_targets=overrides.get("sponsorship_targets", []),
        remote_only=overrides.get("remote_only", True),
        wants_local_onsite=overrides.get("wants_local_onsite", False),
    )

    diagnostics = {
        "skills_found": len(skills),
        "top_skills": sorted(skills, key=lambda s: -skills[s])[:12],
        "years": years,
        "total_years": total_years,
        "level": level,
        "families": families,
        "family_scores": family_scores,
        "country": country,
        "email": find_email(text),
        "text_chars": len(text or ""),
        # A resume this thin usually means a scanned PDF with no text layer.
        "thin": len(text or "") < 400 or len(skills) < 2,
    }
    return profile, diagnostics


def profile_to_dict(p):
    return {
        "user_id": p.user_id, "role_families": p.role_families,
        "strong_skills": p.strong_skills, "adjacent_hints": p.adjacent_hints,
        "min_skill_hits": p.min_skill_hits,
        "years_experience": p.years_experience, "level": p.level,
        "home_country": p.home_country, "authorized_in": p.authorized_in,
        "sponsorship_targets": p.sponsorship_targets,
        "remote_only": p.remote_only, "wants_local_onsite": p.wants_local_onsite,
        "family_skills": p.family_skills,
        "has_clearance": p.has_clearance, "utc_offset": p.utc_offset,
        "min_score": p.min_score, "strong_margin": p.strong_margin,
    }


def profile_from_dict(d):
    return Profile(**d)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python resume_parse.py <resume file>")
        raise SystemExit(2)
    txt = extract_text(sys.argv[1], sys.argv[1])
    prof, diag = parse_profile(txt)
    print("chars       ", diag["text_chars"])
    print("families    ", diag["families"])
    print("years       ", diag["years"], " level:", diag["level"])
    print("country     ", diag["country"])
    print("skills (%d) " % diag["skills_found"], diag["top_skills"])
    print("min_hits    ", prof.min_skill_hits)
    print("thin?       ", diag["thin"])
