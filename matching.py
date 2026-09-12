# -*- coding: utf-8 -*-
"""
Profile-parameterised job scoring.

This is the keystone of TheJobStash and it differs from JobHunt/jobhunt.py's
score() in four ways that matter:

  1. The profile is an argument, not an import, so one process scores many
     users against one shared pool of jobs.

  2. Gates collect *blockers* instead of returning early. In JobHunt a job that
     fails any check returns score 0, which means a perfect React role that
     happens to be onsite in Berlin is indistinguishable from a nursing
     vacancy - both are zero. Here every job that is plausibly this person's
     profession gets a real score AND a list of exactly what stopped it, which
     is what makes the "came close" section of the digest rankable.

  3. Seniority is a distance between two levels plus a parsed years figure,
     not a list of forbidden title words. JobHunt never reads years at all: a
     posting titled "Frontend Developer" whose body demands 8+ years sails
     straight through. That is fixed here.

  4. Exactly one check still excludes outright - role family. A nursing
     vacancy is not a near-miss for a developer, and padding a thin day with
     those is what would genuinely make the product look lazy.

Tone rule, enforced by convention in every Blocker.detail written below: the
string describes the ROLE, never a deficiency in the reader. "Also wanted
GraphQL", not "you do not know GraphQL". People read these on bad days.
"""
import re
from dataclasses import dataclass, field

from profiles import (
    LEVEL_RANK, level_from_years,
    GENERIC_LOCATIONS, OPEN_WORLD_TOKENS, BODY_OPEN_TOKENS,
    SPONSORSHIP_SIGNALS, SPONSOR_NEGATORS, AUTHORISATION_REQUIRED,
    CLEARANCE_MARKERS, ONSITE_ONLY_MARKERS,
)

# How much each reachable geography tier is worth. Sponsorship outranks
# everything because it is the only tier that changes a five-year picture.
GEO_BONUS = {
    "sponsorship":  14,
    "remote_open":   6,
    "home_remote":   3,
    "home_onsite":   2,
}

AUTH_LABEL = {
    "us": "US", "uk": "UK", "eu": "EU", "ca": "Canadian", "au": "Australian",
    "nz": "New Zealand", "in": "Indian", "br": "Brazilian", "za": "South African",
    "de": "German", "pl": "Polish", "ua": "Ukrainian", "cn": "Chinese",
    "latam": "LATAM", "americas": "Americas",
}

# Blockers worth showing in the digest. A skill_gap on its own means the role
# centres on a technology the resume never claimed - that is a different job,
# not a near-miss, so it only earns a slot if the score is strong anyway.
SHOWABLE_BLOCKERS = {"geography", "seniority", "thin_skills",
                     "authorisation", "onsite"}


@dataclass
class Blocker:
    kind: str          # geography | seniority | thin_skills | skill_gap |
                       # authorisation | onsite | clearance
    detail: str        # user-facing, about the role, never about the person


@dataclass
class Match:
    job: dict
    score: int
    tier: str                              # strong | worth_a_look | stretch |
                                           # near_miss
    geo: str
    blockers: list = field(default_factory=list)
    reasons: list = field(default_factory=list)

    @property
    def is_match(self):
        return not self.blockers

    @property
    def showable(self):
        """Whether this earns a slot in the digest at all."""
        if not self.blockers:
            return True
        return any(b.kind in SHOWABLE_BLOCKERS for b in self.blockers)

    @property
    def blocker_kinds(self):
        return sorted({b.kind for b in self.blockers})


# ---------------------------------------------------------------------------
# text helpers
# ---------------------------------------------------------------------------

def tok(needle, haystack):
    """Word-boundary containment, so 'go' does not match 'golang'."""
    return re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])",
                     haystack) is not None


# The remote boards state a timezone window far more often than they state
# eligible countries, and reading it as a place name throws away real matches:
# "Timezone restricted (UTC-10 to UTC+14)" is the entire planet, not a
# restriction. It also produces an unusable sentence in a paid email.
_TZ_RANGE = re.compile(
    r"utc\s*([+-]\s*\d{1,2})(?:\s*(?::\d{2})?)?\s*(?:to|[-–—])\s*"
    r"utc\s*([+-]\s*\d{1,2})", re.I)
_TZ_SINGLE = re.compile(r"utc\s*([+-]\s*\d{1,2})", re.I)


def timezone_window(location):
    """(low, high) UTC offsets a posting allows, or None if it names none."""
    text = (location or "").lower()
    m = _TZ_RANGE.search(text)
    if m:
        try:
            lo = int(m.group(1).replace(" ", ""))
            hi = int(m.group(2).replace(" ", ""))
        except (TypeError, ValueError):
            return None
        return (min(lo, hi), max(lo, hi))
    if "timezone" in text or "time zone" in text:
        hits = [int(h.replace(" ", "")) for h in _TZ_SINGLE.findall(text)]
        if hits:
            return (min(hits), max(hits))
    return None


def pretty_location(location):
    """The location as it should appear in a sentence sent to a paying user."""
    raw = (location or "").strip()
    if not raw:
        return "an unnamed location"
    win = timezone_window(raw)
    if win:
        lo, hi = win
        fmt = lambda n: "UTC%+d" % n
        return ("the %s timezone" % fmt(lo) if lo == hi
                else "timezones %s to %s" % (fmt(lo), fmt(hi)))
    # Boards repeat themselves - "USA, Canada, USA timezones" - and the repeat
    # reads as carelessness on our side rather than theirs.
    seen, parts = set(), []
    for p in re.split(r"\s*,\s*", raw):
        p = re.sub(r"\s+timezones?$", "", p.strip(), flags=re.I)
        key = p.lower()
        if p and key not in seen:
            seen.add(key)
            parts.append(p)
    return ", ".join(parts) or raw


def _loc_parts(location):
    """Split a location field into the individual places it names.

    The or/and separators must be word-bounded: written bare they match INSIDE
    country names ("Poland" -> "pol", "Ireland" -> "irel").
    """
    return [p.strip() for p in re.split(r"[,/|;()•]|\bor\b|\band\b",
                                        (location or "").lower()) if p.strip()]


# ---------------------------------------------------------------------------
# years of experience - absent entirely from JobHunt, and a prerequisite for
# the "asks for 5+ years" near-miss reason to exist at all
# ---------------------------------------------------------------------------

_YEARS_RE = re.compile(
    r"(?<![\d.,])(\d{1,2})\s*(?:\+|plus)?\s*"
    r"(?:(?:[-–—]|to)\s*(\d{1,2})\s*\+?)?\s*(?:years?|yrs?)\b",
    re.I)

# Phrases meaning the number is NOT a requirement on the candidate. Without
# these, "serving clients for 15 years" reads as a 15-year requirement.
_YEARS_NEGATIVE = re.compile(
    r"\b(in business|we have been|we've been|founded|established|anniversary|"
    r"history|funded|ago|operating|serving|since|over the past|for the last|"
    r"years old|track record of \d)\b", re.I)

_YEARS_POSITIVE = re.compile(
    r"\b(experien\w+|background|professional|hands[- ]?on|working|industry|"
    r"commercial|practical|minimum|at least|required|requirement|proven|"
    r"must have|looking for|seeking)\b", re.I)


def parse_years_required(text):
    """Lowest number of years the posting appears to demand, or None.

    The minimum is taken deliberately: a posting saying "3+ years React, 5+
    years overall" has an entry bar of three, and being generous here is the
    difference between a near-miss the user might actually win and a silent
    rejection.
    """
    if not text:
        return None
    found = []
    for m in _YEARS_RE.finditer(text):
        window = text[max(0, m.start() - 70): m.end() + 50]
        if _YEARS_NEGATIVE.search(window) and not _YEARS_POSITIVE.search(window):
            continue
        try:
            n = int(m.group(1))
        except (TypeError, ValueError):
            continue
        if 0 <= n <= 20:                  # above 20 is prose, not a requirement
            found.append(n)
    return min(found) if found else None


# ---------------------------------------------------------------------------
# seniority level
# ---------------------------------------------------------------------------

# Order matters: the most specific wins, so "Senior Staff Engineer" reads as
# principal rather than senior, and "Senior Engineering Manager" as lead.
_TITLE_LEVEL = [
    ("exec",      r"\b(chief|cto|cio|ceo|cpo|vp|vice president|head of)\b"),
    ("principal", r"\b(principal|distinguished|staff engineer|staff developer|"
                  r"staff software|architect)\b"),
    ("lead",      r"\b(team lead|tech lead|technical lead|lead engineer|"
                  r"lead developer|lead software|engineering manager|"
                  r"development manager|lead(?!\s*(generation|gen\b)))\b"),
    ("intern",    r"\b(intern|internship|trainee|apprentice)\b"),
    ("junior",    r"\b(junior|jr\.?|entry.level|graduate|associate)\b"),
    ("senior",    r"\b(senior|sr\.?)\b"),
]

# The boards' own seniority field, which arrives as a mess: 72% empty and the
# rest a mix of real labels and unmapped numeric codes ('400', '200', '300').
_SENIORITY_MAP = {
    "intern": "intern", "internship": "intern", "trainee": "intern",
    "entry level": "junior", "entry-level": "junior", "junior": "junior",
    "associate": "junior", "graduate": "junior",
    "mid": "mid", "mid-level": "mid", "mid level": "mid",
    "intermediate": "mid", "experienced": "mid",
    "senior": "senior", "senior level": "senior",
    "lead": "lead", "manager": "lead", "supervisor": "lead",
    "director": "exec", "executive": "exec", "vp": "exec", "chief": "exec",
}


def normalise_seniority(raw):
    """Map a board's seniority field onto the scale, or None if it is noise."""
    key = (raw or "").strip().lower()
    if not key or key.isdigit():          # numeric codes carry no meaning here
        return None
    return _SENIORITY_MAP.get(key)


def detect_level(title, seniority_field=None, years=None):
    """Best available read of how senior a posting is.

    Title first because it is the most deliberate signal, then the board's own
    field, then the years figure as a last resort.
    """
    low = (title or "").lower()
    for level, pattern in _TITLE_LEVEL:
        if re.search(pattern, low):
            return level
    return normalise_seniority(seniority_field) or level_from_years(years)


# ---------------------------------------------------------------------------
# geography
# ---------------------------------------------------------------------------

def sponsorship_offered(hay):
    """True only if sponsorship is OFFERED, not merely mentioned.

    Most postings containing "visa sponsorship" are refusing it. Matching the
    phrase alone promotes exactly the wrong roles to the top tier, so every hit
    is checked for a negation cue in the surrounding text first.
    """
    for sig in SPONSORSHIP_SIGNALS:
        for m in re.finditer(re.escape(sig), hay):
            window = hay[max(0, m.start() - 80): m.end() + 80]
            if any(n in window for n in SPONSOR_NEGATORS):
                continue                  # mentioned in order to refuse it
            return True
    return False


def reachable_location(location, profile):
    """Read the board's location field, which is the authoritative signal.

    Returns "open" (worldwide / the user's country / their region), "closed"
    (names only places they cannot work), or "unknown" (says nothing useful,
    so the body has to be read instead).
    """
    hq = re.search(r"\[hq:\s*([^\]]+)\]", (location or "").lower())
    if hq:                                # an explicit HQ annotation overrides
        location = hq.group(1)            # the board's own region label

    # A timezone window is a real answer, so it settles the question outright
    # rather than falling through to be misread as a place name.
    win = timezone_window(location)
    if win:
        lo, hi = win
        return "open" if lo <= profile.utc_offset <= hi else "closed"

    parts = _loc_parts(location)
    if not parts or all(p in GENERIC_LOCATIONS for p in parts):
        return "unknown"
    for p in parts:
        if p in GENERIC_LOCATIONS:
            continue
        if any(t in p for t in OPEN_WORLD_TOKENS):
            return "open"
        if any(t in p for t in profile.home_tokens):
            return "open"
        if any(tok(t, p) for t in profile.region_tokens):
            return "open"
        if any(t in p for t in profile.sponsorship_tokens):
            return "open"                 # reachable if a visa is on the table
    return "closed"                       # named real places, none reachable


def classify_geo(job, profile):
    """Return (tier, Blocker or None).

    Allowlist, not denylist: a posting is only reachable if something
    positively says so. Naming any other country closes it whether or not the
    word "only" appears.
    """
    loc = (job.get("location") or "").lower()
    body = (job.get("description") or "").lower()
    hay = loc + " " + body
    shown_loc = pretty_location(job.get("location"))
    tz_win = timezone_window(job.get("location"))

    # What authorisation does this posting demand, and does the user hold it?
    # This replaces JobHunt's flat blocker list: "us citizen" stops Justin and
    # does not stop an American.
    for code, phrases in AUTHORISATION_REQUIRED.items():
        if code in profile.authorized_in:
            continue
        if any(p in hay for p in phrases):
            return "blocked", Blocker(
                "authorisation",
                "Requires %s work authorisation" % AUTH_LABEL.get(code, code.upper()))

    if not profile.has_clearance and any(m in hay for m in CLEARANCE_MARKERS):
        return "blocked", Blocker("clearance",
                                  "Requires a government security clearance")

    # Sponsorship outranks everything, but only for users who actually want it.
    if profile.wants_sponsorship and sponsorship_offered(hay):
        return "sponsorship", None

    remote = ("remote" in hay or "worldwide" in hay or "anywhere" in hay
              or "distributed" in hay)

    if profile.remote_only and any(m in hay for m in ONSITE_ONLY_MARKERS):
        return "blocked", Blocker("onsite", "This role is onsite only")

    where = reachable_location(job.get("location"), profile)
    loc_home = any(t in loc for t in profile.home_tokens)

    # Home-country status is decided by the LOCATION field, not the body. A
    # global role that merely lists the user's country among eligible ones is a
    # foreign remote role open to them, which outranks a local one.
    if loc_home and not remote:
        if profile.wants_local_onsite:
            return "home_onsite", None
        return "blocked", Blocker("geography", "Onsite in %s" % shown_loc)
    if loc_home and remote:
        return "home_remote", None

    if where == "closed":
        if tz_win:
            return "blocked", Blocker(
                "geography", "Limited to %s, and you are on UTC%+d"
                             % (shown_loc, profile.utc_offset))
        return "blocked", Blocker("geography", "Hiring in %s" % shown_loc)

    if where == "open" and remote:
        return "remote_open", None

    if where == "unknown" and any(t in hay for t in profile.home_tokens):
        if remote:
            return "home_remote", None
        if profile.wants_local_onsite:
            return "home_onsite", None
        return "blocked", Blocker("geography", "Onsite in %s" % shown_loc)

    # The board told us nothing. Require the body to claim open-to-anywhere
    # rather than assuming it, which is what lets a Chile-only role pass.
    if remote and any(t in hay for t in BODY_OPEN_TOKENS):
        return "remote_open", None

    return "blocked", Blocker("geography",
                              "Does not say it is open to your location")


# ---------------------------------------------------------------------------
# the scorer
# ---------------------------------------------------------------------------

def score(job, profile):
    """Score one job for one user.

    Returns a Match, or None when the posting is not this person's profession
    at all - the single remaining outright exclusion.
    """
    title = (job.get("title") or "").lower()
    body = (title + " " + (job.get("description") or "")).lower()

    if not any(re.search(p, title) for p in profile.role_families):
        return None

    pts, reasons, blockers = 0, [], []

    # -- geography ----------------------------------------------------------
    geo_tier, geo_block = classify_geo(job, profile)
    if geo_block:
        blockers.append(geo_block)
    else:
        bonus = GEO_BONUS.get(geo_tier, 0)
        pts += bonus
        reasons.append("%s (+%d)" % (geo_tier.replace("_", " "), bonus))

    # -- skills, ALWAYS computed even when a gate above already failed ------
    hits = sorted({s for s in profile.strong_skills if tok(s.lower(), body)})
    for s in hits:
        pts += profile.strong_skills[s]
    if hits:
        reasons.append("matches " + ", ".join(hits[:12]))
    if len(hits) < profile.min_skill_hits:
        wanted = [t for t in profile.unshipped if tok(t, body)][:3]
        detail = ("Also wanted " + ", ".join(wanted) if wanted
                  else "Overlaps with only %d of your listed skills" % len(hits))
        blockers.append(Blocker("thin_skills", detail))

    # -- seniority ----------------------------------------------------------
    years_req = parse_years_required(body)
    job_level = detect_level(title, job.get("seniority"), years_req)
    if job_level:
        gap = LEVEL_RANK[job_level] - profile.level_rank
        if gap >= 2:
            blockers.append(Blocker("seniority", "This is a %s role" % job_level))
        elif gap == 1:
            pts -= 6
            reasons.append("a step up to %s (-6)" % job_level)
        elif gap <= -2:
            blockers.append(Blocker("seniority",
                                    "Pitched at %s level" % job_level))
    if years_req is not None:
        if years_req > profile.years_experience + 2:
            blockers.append(Blocker("seniority", "Asks for %d+ years" % years_req))
        elif years_req > profile.years_experience:
            pts -= 4
            reasons.append("asks for %d+ years (-4)" % years_req)

    # -- technology the resume never claimed --------------------------------
    # In the title it is the point of the role, which is a different job.
    for gap_tech in profile.unshipped:
        if re.search(r"(?<![a-z0-9])" + re.escape(gap_tech), title):
            blockers.append(Blocker("skill_gap", "Centres on %s" % gap_tech))
            break

    if any(h in title for h in profile.adjacent_hints):
        pts += 4
        reasons.append("adjacent role you qualify for (+4)")

    # In the body only it is probably secondary, so a nudge rather than a cut.
    body_gaps = [g for g in profile.unshipped if tok(g, body)
                 and not tok(g, title)]
    if body_gaps:
        pts -= min(len(body_gaps) * 2, 8)
        reasons.append("also mentions " + ", ".join(body_gaps[:5]))

    # -- tier ---------------------------------------------------------------
    if blockers:
        tier = "near_miss"
    elif pts >= profile.min_score + profile.strong_margin:
        tier = "strong"
    elif pts >= profile.min_score:
        tier = "worth_a_look"
    else:
        tier = "stretch"

    return Match(job=job, score=pts, tier=tier, geo=geo_tier,
                 blockers=blockers, reasons=reasons)


def score_many(jobs, profile):
    """Score a pool, dropping only what is not this person's profession.

    Sorted best-first. Near-misses keep their real score, so the digest can
    take the top few rather than whichever happened to be scraped first.
    """
    out = []
    for j in jobs:
        m = score(j, profile)
        if m is not None:
            out.append(m)
    out.sort(key=lambda m: (m.is_match, m.score), reverse=True)
    return out
