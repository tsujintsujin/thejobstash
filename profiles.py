# -*- coding: utf-8 -*-
"""
What a TheJobStash user *is*, as data.

JobHunt/profile.py is one person hard-coded into a module. This is the same
information shaped so a single process can hold many of them at once, which is
the entire difference between a personal tool and a product.

Three things are generalised rather than copied:

  * Work authorisation replaces a flat blocker list. "us citizen" blocks Justin
    and does not block an American, so a posting's *requirement* is detected
    and then checked against what the user actually holds.
  * Unshipped technology is derived by inversion. JobHunt/profile.py lists 89
    things Justin has never shipped, which nobody will fill in by hand at
    signup. Here it is TECH_VOCAB minus whatever the resume claimed.
  * Seniority is a level plus years, not a list of forbidden titles. "Lead" is
    wrong for a mid-level user and correct for a lead-level one.

JobHunt/ is not imported by the product path and never modified. Justin's daily
sweep keeps its own scorer.
"""
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Seniority as an ordered scale, so the distance between two levels is a number
# ---------------------------------------------------------------------------
LEVELS = ["intern", "junior", "mid", "senior", "lead", "principal", "exec"]
LEVEL_RANK = {name: i for i, name in enumerate(LEVELS)}


def level_from_years(years):
    """Fallback when a posting names no level but does name a number."""
    if years is None:
        return None
    if years <= 1:
        return "junior"
    if years <= 4:
        return "mid"
    if years <= 7:
        return "senior"
    return "lead"


# ---------------------------------------------------------------------------
# Geography vocabulary that is genuinely universal - true regardless of who is
# reading the posting. Anything that depends on the reader lives on Profile.
# ---------------------------------------------------------------------------
GENERIC_LOCATIONS = [
    "", "remote", "remote job", "fully remote", "see posting", "n/a", "none",
    "various", "multiple locations", "unspecified", "homeoffice (remote)",
]

OPEN_WORLD_TOKENS = [
    "worldwide", "anywhere", "global", "globally", "international",
    "work from anywhere", "location independent", "any location", "any country",
    "no location requirement", "remote - global",
]

BODY_OPEN_TOKENS = [
    "anywhere in the world", "work from anywhere", "from anywhere in",
    "worldwide", "any country", "location independent", "no location requirement",
    "globally distributed", "fully distributed", "work from any",
    "remote (global)", "remote - global", "remote global",
]

SPONSORSHIP_SIGNALS = [
    "visa sponsorship", "sponsor a visa", "will sponsor", "sponsorship available",
    "sponsor your visa", "visa support", "work permit sponsorship",
    "accredited employer", "aewv", "482 visa", "skills in demand visa",
    "green list", "relocation and visa",
]

# Most postings containing "visa sponsorship" are refusing it. Every hit is
# checked for one of these in the surrounding text before it counts.
SPONSOR_NEGATORS = [
    "not available", "unable", "cannot", "can not", "can not", "will not",
    "do not", "does not", "not able", "not offer", "not offering", "not provide",
    "not providing", "without", "ineligible", "not sponsor", "no longer",
    "not consider", "not support", "excluded", "not in a position", "no visa",
    "no sponsorship", "not eligible", "must already",
]

# A posting that demands the right to work somewhere specific. The phrase maps
# to the authorisation it demands, which is then checked against the user's.
# This is the generalisation of JobHunt's flat BLOCKERS list: the same string
# that stops Justin does not stop somebody who holds that authorisation.
AUTHORISATION_REQUIRED = {
    "us": ["us citizen", "u.s. citizen", "united states only", "usa only",
           "us only", "must be located in the united states",
           "must be based in the us", "us work authorization",
           "authorized to work in the united states", "green card"],
    "uk": ["uk right to work", "right to work in the united kingdom",
           "uk only", "must have the right to work in the uk"],
    "eu": ["eu citizens only", "eu only", "europe only", "emea only",
           "eu work authorization", "right to work in the eu"],
    "ca": ["canada only", "must be located in canada", "canadian citizen"],
    "au": ["australia only", "australian citizen",
           "must have australian work rights"],
    "nz": ["new zealand only", "nz citizen"],
    "in": ["india only"],
    "br": ["brazil only"],
    "za": ["south africa only"],
    "de": ["germany only"],
    "pl": ["poland only"],
    "ua": ["ukraine only"],
    "cn": ["china only"],
    "latam": ["latam only"],
    "americas": ["americas only"],
}

# Blockers that apply to essentially everyone unless the profile says otherwise.
CLEARANCE_MARKERS = ["security clearance", "ts/sci", "public trust clearance"]
ONSITE_ONLY_MARKERS = ["onsite only", "on-site only", "no remote",
                       "must relocate", "in-office only"]

# Country -> the strings that mean that country in a location field. Cities are
# included where a board is likely to name one instead of the country.
COUNTRY_TOKENS = {
    "philippines": ["philippines", "filipino", "manila", "metro manila",
                    "makati", "taguig", "quezon city", "cebu", "davao", "bgc",
                    "pasig", "mandaluyong", "iloilo"],
    "united states": ["united states", "usa", "u.s.", "us-based", "america",
                      "new york", "san francisco", "austin", "seattle",
                      "chicago", "boston", "los angeles", "denver"],
    "united kingdom": ["united kingdom", "uk", "england", "london",
                       "manchester", "scotland", "wales"],
    "canada": ["canada", "toronto", "vancouver", "montreal", "ottawa"],
    "australia": ["australia", "sydney", "melbourne", "brisbane", "perth"],
    "new zealand": ["new zealand", "aotearoa", "auckland", "wellington"],
    "india": ["india", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad"],
    "germany": ["germany", "berlin", "munich", "hamburg"],
    "singapore": ["singapore"],
    "indonesia": ["indonesia", "jakarta"],
    "vietnam": ["vietnam", "hanoi", "ho chi minh"],
    "malaysia": ["malaysia", "kuala lumpur"],
}

# Country -> the regional labels that include it. A posting open to "APAC" is
# open to someone in Manila.
REGION_TOKENS = {
    "philippines": ["apac", "asia pacific", "asia-pacific", "southeast asia",
                    "south east asia", "south-east asia", "asia", "asean",
                    "aseans"],
    "singapore": ["apac", "asia pacific", "asia-pacific", "southeast asia",
                  "asia", "asean"],
    "indonesia": ["apac", "asia pacific", "southeast asia", "asia", "asean"],
    "vietnam": ["apac", "asia pacific", "southeast asia", "asia", "asean"],
    "malaysia": ["apac", "asia pacific", "southeast asia", "asia", "asean"],
    "india": ["apac", "asia pacific", "asia", "south asia"],
    "united states": ["north america", "americas", "namer"],
    "canada": ["north america", "americas", "namer"],
    "united kingdom": ["europe", "emea"],
    "germany": ["europe", "emea", "dach"],
    "australia": ["apac", "asia pacific", "anz", "oceania"],
    "new zealand": ["apac", "asia pacific", "anz", "oceania"],
}

# Country -> that country's UTC offset, used to read the timezone windows the
# remote boards attach to postings ("Timezone restricted (UTC-4 to UTC-4)").
# Approximate and DST-naive on purpose: an hour either way never decides
# whether somebody in Manila can take a UTC-4-only role.
COUNTRY_UTC = {
    "philippines": 8, "singapore": 8, "malaysia": 8, "indonesia": 7,
    "vietnam": 7, "india": 5, "united states": -6, "canada": -5,
    "united kingdom": 0, "germany": 1, "australia": 10, "new zealand": 12,
}

# Country -> the authorisation code a posting would demand for it.
COUNTRY_AUTH = {
    "philippines": "ph", "united states": "us", "united kingdom": "uk",
    "canada": "ca", "australia": "au", "new zealand": "nz", "india": "in",
    "germany": "eu", "brazil": "br", "south africa": "za", "poland": "eu",
    "ukraine": "ua", "china": "cn", "singapore": "sg",
}

# Every technology the matcher knows how to recognise. A user's "never shipped"
# set is this minus what their resume claimed - nobody fills in 89 checkboxes.
TECH_VOCAB = [
    "java", "spring", "kotlin", "scala", "python", "django", "flask", "fastapi",
    "golang", "rust", "c++", "c#", ".net", "dotnet", "ruby", "rails", "elixir",
    "phoenix", "perl", "php", "laravel", "flutter", "dart", "swift", "ios",
    "android", "react native", "angular", "vue", "svelte", "ember", "react",
    "next.js", "nuxt", "typescript", "javascript", "node", "express",
    "tailwind", "shopify", "liquid", "magento", "bigcommerce", "wordpress",
    "power bi", "dax", "tableau", "looker", "qlik", "salesforce", "servicenow",
    "sap", "oracle", "dynamics 365", "sharepoint", "kubernetes", "terraform",
    "ansible", "openshift", "docker", "aws", "azure", "gcp", "mongodb",
    "cassandra", "dynamodb", "postgres", "postgresql", "mysql", "redis",
    "graphql", "bigquery", "vertex ai", "databricks", "snowflake",
    "airflow", "hadoop", "spark", "unity", "unreal", "solidity", "web3",
    "blockchain", "smart contract", "machine learning", "deep learning",
    "pytorch", "tensorflow", "nlp", "devops", "sre", "site reliability",
    "platform engineer", "infrastructure engineer", "security engineer",
    "cybersecurity", "penetration", "cloud engineer", "data scientist",
    "network engineer", "systems administrator", "sysadmin", "embedded",
    "firmware", "hardware", "electrical", "mechanical", "figma",
]


@dataclass
class Profile:
    """One user. Everything the matcher needs, nothing it does not."""

    user_id: str = "anonymous"

    # --- what they do -------------------------------------------------------
    # Regex patterns. A posting whose title matches none of these is not this
    # person's job at all and is excluded outright rather than shown as a
    # near-miss - a nursing vacancy is not a near-miss for a developer.
    role_families: list = field(default_factory=list)
    # skill -> weight. Weight is how strongly it argues for them.
    strong_skills: dict = field(default_factory=dict)
    # Skills the user switched off on the dashboard. Kept in strong_skills as
    # stored so the dashboard can still list and re-enable them; dropped here
    # in __post_init__ so every consumer of a loaded Profile - scoring,
    # unshipped, family_skills - sees one already-filtered set rather than
    # each having to remember the exclusion.
    disabled_skills: list = field(default_factory=list)
    # Roles they would still clear even though the title is not a dev title.
    adjacent_hints: list = field(default_factory=list)
    min_skill_hits: int = 3

    # --- how senior they are ------------------------------------------------
    # None means the resume gave no usable employment dates. Unknown must stay
    # unknown and must never gate - see score()'s seniority block.
    years_experience: int = None
    level: str = "mid"

    # --- where they can work ------------------------------------------------
    home_country: str = "philippines"
    # Authorisation codes they hold. Defaults to their home country's code.
    authorized_in: list = field(default_factory=list)
    # Countries they would relocate to if a visa were offered. Empty means the
    # sponsorship tier is switched off for this user.
    sponsorship_targets: list = field(default_factory=list)
    remote_only: bool = True          # False = local onsite roles are welcome
    wants_local_onsite: bool = False
    # Skills belonging to this profile's own role families. Used to decide
    # whether a thin skill overlap is real evidence or cross-career noise:
    # "excel" is a core admin skill and an incidental one for a developer,
    # and without this distinction an RPA developer role matched a teacher's
    # profile on the word excel alone. Empty for older stored profiles, which
    # simply skips the check.
    family_skills: list = field(default_factory=list)
    has_clearance: bool = False
    # None = derive from home_country. Boards state timezone windows far more
    # often than they state eligible countries, so this is load-bearing.
    utc_offset: int = None

    # --- scoring dials ------------------------------------------------------
    min_score: int = 12
    strong_margin: int = 12           # strong = min_score + this

    def __post_init__(self):
        if self.disabled_skills:
            off = {s.lower() for s in self.disabled_skills}
            self.strong_skills = {k: v for k, v in self.strong_skills.items()
                                  if k.lower() not in off}
            self.family_skills = [s for s in self.family_skills
                                  if s.lower() not in off]
        # A bar of three against two skills can never be cleared, so a run
        # would burn a credit and return nothing. Holds for thin resumes too,
        # not just switched-off skills.
        if self.strong_skills:
            self.min_skill_hits = min(self.min_skill_hits,
                                      len(self.strong_skills))
        if not self.authorized_in:
            self.authorized_in = [COUNTRY_AUTH.get(self.home_country,
                                                   self.home_country)]
        if self.level not in LEVEL_RANK:
            self.level = "mid"
        if self.utc_offset is None:
            self.utc_offset = COUNTRY_UTC.get(self.home_country, 0)

    # -- derived vocabulary --------------------------------------------------
    @property
    def home_tokens(self):
        return COUNTRY_TOKENS.get(self.home_country, [self.home_country])

    @property
    def region_tokens(self):
        return REGION_TOKENS.get(self.home_country, [])

    @property
    def unshipped(self):
        """TECH_VOCAB minus what they claim. The inversion described up top."""
        claimed = {s.lower() for s in self.strong_skills}
        return [t for t in TECH_VOCAB if t not in claimed]

    @property
    def level_rank(self):
        return LEVEL_RANK[self.level]

    @property
    def wants_sponsorship(self):
        return bool(self.sponsorship_targets)

    @property
    def sponsorship_tokens(self):
        """Location strings for the countries this user would relocate to."""
        out = []
        for c in self.sponsorship_targets:
            out += COUNTRY_TOKENS.get(c, [c])
        return out


def from_jobhunt_profile(mod, user_id="justin"):
    """Adapt JobHunt/profile.py into a Profile, for parity testing only.

    Read-only: the module is imported and inspected, never written to. This
    exists so the new scorer can be checked against the one profile whose
    results are already known, before any real user exists.
    """
    return Profile(
        user_id=user_id,
        role_families=list(mod.ROLE_FAMILIES),
        strong_skills=dict(mod.STRONG_SKILLS),
        adjacent_hints=list(mod.ADJACENT_ROLE_HINTS),
        min_skill_hits=mod.MIN_SKILL_HITS,
        years_experience=mod.YEARS_EXPERIENCE,
        level="mid",
        home_country="philippines",
        authorized_in=["ph"],
        sponsorship_targets=["australia", "new zealand"],
        remote_only=True,
        wants_local_onsite=False,
        min_score=mod.MIN_SCORE,
    )
