/**
 * The words on each /jobs/<slug> page. The numbers and example postings come
 * from D1 (pool_pages, written by pool_pages.py); these are the parts a
 * number cannot say. Slugs must match pool_pages.FAMILIES. A slug here with no
 * D1 row 404s; a D1 row with no entry here falls back to generic copy.
 *
 * Every page gets its own intro and its own "what gets people filtered out",
 * because sixteen pages that differ only in a noun are exactly the thin,
 * templated content search engines demote.
 */
export type RoleCopy = {
  /** Used in the title and H1: "<plural> jobs in the Philippines". */
  plural: string;
  intro: string;
  /** What employers in this family ask for, most often first. */
  asks: string[];
  /** The mismatches that most often knock applicants out. */
  blockers: string[];
};

export const ROLE_COPY: Record<string, RoleCopy> = {
  remote: {
    plural: "Remote and work-from-home",
    intro:
      "Most of the pool is remote work open to people in the Philippines: " +
      "roles posted by overseas companies, and local employers hiring for " +
      "work-from-home. Remote does not mean anywhere, though. A lot of " +
      "'remote' postings quietly limit who can apply by country, timezone or " +
      "work authorisation, and that is where most applications are wasted.",
    asks: [
      "Reliable internet and a backup connection or power source",
      "Overlap with a US, Australian or European working day",
      "Written English good enough for async work in chat and email",
      "Experience with the employer's tools, named in the posting",
    ],
    blockers: [
      "Remote, but only for residents of one country",
      "A shift window you cannot cover from Philippine time",
      "Work authorisation you do not hold (common on US-based boards)",
    ],
  },
  "virtual-assistant": {
    plural: "Virtual assistant",
    intro:
      "Virtual assistant work is the largest single kind of remote job " +
      "posted for Filipinos, and the widest: an executive assistant managing " +
      "a founder's calendar, an e-commerce VA running an Amazon or Shopify " +
      "store, a medical VA handling intake and insurance, a real-estate VA " +
      "setting appointments. The title is the same; the jobs are not, which " +
      "is why a generic VA resume matches badly against most of them.",
    asks: [
      "Named tools: Google Workspace, QuickBooks, Shopify, Amazon Seller Central, GoHighLevel, CRMs",
      "Industry experience (medical, real estate, e-commerce, legal)",
      "Calendar and inbox management for an executive",
      "Availability during US hours",
    ],
    blockers: [
      "An industry specialism you have not worked in",
      "A specific platform the whole role runs on",
      "US-hours shifts the applicant cannot cover",
    ],
  },
  "customer-service": {
    plural: "Customer service",
    intro:
      "Customer service covers chat, email and voice support, both at " +
      "Philippine BPOs and for overseas brands hiring support staff directly. " +
      "Direct-hire roles often pay better than BPO seats but ask for more: " +
      "a specific helpdesk tool, a second language, or experience with the " +
      "product's market.",
    asks: [
      "Voice or non-voice (chat and email) experience, stated clearly",
      "Helpdesk tools such as Zendesk, Gorgias, Freshdesk or Intercom",
      "A second language for some accounts",
      "Night-shift availability for US and UK customers",
    ],
    blockers: [
      "Voice experience asked for when the applicant has only done chat",
      "Onsite roles at a site outside the applicant's city",
      "A language requirement",
    ],
  },
  sales: {
    plural: "Sales and business development",
    intro:
      "Sales roles range from appointment setting and cold calling for US " +
      "businesses to account executive and business development positions " +
      "at Philippine companies. Pay is often part base, part commission, and " +
      "the posting's pay line does not always make clear which.",
    asks: [
      "Outbound experience: cold calling, email sequences, lead generation",
      "A CRM: HubSpot, Salesforce, GoHighLevel, Pipedrive",
      "Industry background (real estate, insurance, SaaS, solar)",
      "Quota or target history",
    ],
    blockers: [
      "Commission-only pay presented as a salary",
      "An industry the applicant has never sold into",
      "Years of closing experience asked of an appointment setter",
    ],
  },
  marketing: {
    plural: "Marketing and social media",
    intro:
      "Marketing covers social media management, content, SEO, paid ads and " +
      "email. Employers are increasingly specific about the channel. A " +
      "posting for 'marketing' is often really a Meta Ads role or a TikTok " +
      "content role, and a resume that lists everything matches none of them " +
      "well.",
    asks: [
      "A named channel: Meta Ads, Google Ads, TikTok, SEO, email",
      "Tools: Canva, Meta Business Suite, Klaviyo, Semrush, Ahrefs",
      "A portfolio or results with numbers",
      "Experience in the employer's niche",
    ],
    blockers: [
      "Paid-ads budgets or results the applicant cannot show",
      "A channel the applicant has not run",
      "Senior strategy roles asking for years of management",
    ],
  },
  accounting: {
    plural: "Accounting and bookkeeping",
    intro:
      "Accounting and bookkeeping are among the best-paid remote work open " +
      "to Filipinos, because overseas firms hire Philippine CPAs and " +
      "bookkeepers for US, Australian and UK books. Those roles almost " +
      "always name the software and the country's standards, and both " +
      "decide who gets a reply.",
    asks: [
      "QuickBooks Online, Xero, MYOB or NetSuite",
      "US GAAP, IFRS or the employer's country's tax rules",
      "Full-cycle bookkeeping: AP, AR, reconciliations, month-end close",
      "CPA licence for senior roles",
    ],
    blockers: [
      "A named accounting package the applicant has not used",
      "Foreign tax or payroll experience",
      "CPA licence required",
    ],
  },
  "software-developer": {
    plural: "Software and web development",
    intro:
      "Developer roles come from Philippine tech companies, overseas " +
      "startups hiring remote, and the international remote boards. The " +
      "stack decides almost everything: a strong React developer is a " +
      "near-miss for a Vue role and a non-match for a Laravel one, however " +
      "many years they have.",
    asks: [
      "A specific stack: React, Next.js, Laravel, Django, .NET, Node",
      "Cloud and deployment: AWS, Docker, CI/CD",
      "Years at a level: mid, senior, lead",
      "Timezone overlap for standups",
    ],
    blockers: [
      "The core framework is one the applicant has not shipped",
      "Senior roles asking for twice the applicant's years",
      "Remote only for residents of the US or EU",
    ],
  },
  "graphic-design": {
    plural: "Graphic design and video",
    intro:
      "Design work covers graphic design, UI/UX, video editing and motion " +
      "work, most of it remote. Almost every posting asks for a portfolio, " +
      "and many name one type of output (short-form video, Amazon listing " +
      "images, brand identity) that the portfolio needs to show.",
    asks: [
      "A portfolio showing the kind of work in the posting",
      "Adobe Creative Suite, Figma, Canva, CapCut or Premiere",
      "Short-form video for TikTok, Reels and YouTube Shorts",
      "Fast turnaround on a daily or weekly volume",
    ],
    blockers: [
      "A portfolio with no example of the requested output",
      "UI/UX roles asking for product design experience",
      "Motion or 3D tools the applicant has not used",
    ],
  },
  writing: {
    plural: "Writing and content",
    intro:
      "Writing roles include content and blog writing, copywriting, " +
      "scriptwriting for YouTube, editing, proofreading and transcription. " +
      "Pay varies more here than almost anywhere, from per-article rates to " +
      "full-time salaries, and samples usually matter more than years.",
    asks: [
      "Writing samples in the employer's format and niche",
      "SEO writing and familiarity with WordPress",
      "YouTube scripting for faceless channels",
      "Native-level English for copywriting roles",
    ],
    blockers: [
      "No samples in the requested niche",
      "Technical or medical subject knowledge",
      "Per-article pay that works out below a living wage",
    ],
  },
  admin: {
    plural: "Admin and data entry",
    intro:
      "Admin and data entry roles are the most accessible on the list: " +
      "office support, encoding, records and back-office work, remote and " +
      "onsite. They are also the most crowded, so a clean resume that names " +
      "the exact systems used is what separates applications.",
    asks: [
      "Excel or Google Sheets, stated with what you did in them",
      "Typing speed and accuracy",
      "A specific system: an ERP, CRM or records platform",
      "Onsite availability for local office roles",
    ],
    blockers: [
      "Onsite in a city the applicant is not in",
      "Advanced Excel asked for when basic use is listed",
      "Industry-specific records (medical, legal, logistics)",
    ],
  },
  "hr-recruitment": {
    plural: "HR and recruitment",
    intro:
      "HR and recruitment roles include recruiters and sourcers for " +
      "overseas agencies, talent acquisition at Philippine companies, and HR " +
      "generalists. Offshore recruiting roles usually name the market " +
      "(US healthcare, IT staffing) and the applicant tracking system.",
    asks: [
      "Full-cycle recruiting or sourcing experience",
      "An ATS such as Bullhorn, Greenhouse, Lever or Workable",
      "A market: US healthcare, IT, engineering, BPO volume hiring",
      "Philippine labor law for local HR generalist roles",
    ],
    blockers: [
      "A recruiting market the applicant has not worked",
      "Local HR roles requiring Philippine labor law and onsite presence",
      "Volume targets from a very different kind of hiring",
    ],
  },
  "project-manager": {
    plural: "Project and operations management",
    intro:
      "Project, product and operations management roles sit at the senior " +
      "end of the pool. They ask for proof of running something end to end, " +
      "and for years at that level. Remote roles here usually need solid " +
      "timezone overlap with the team they lead.",
    asks: [
      "Tools: Jira, Asana, ClickUp, Monday, Notion",
      "Methodology: Agile, Scrum, PMP for some roles",
      "Team size and budget handled, in numbers",
      "Industry experience matching the employer's",
    ],
    blockers: [
      "Years of management experience",
      "A certification (PMP, Scrum Master)",
      "Hours that overlap the team's working day",
    ],
  },
  healthcare: {
    plural: "Healthcare and medical",
    intro:
      "Healthcare roles here are mostly remote support for overseas " +
      "clinics: medical virtual assistants, billing and coding, insurance " +
      "verification and intake. A nursing or allied-health background " +
      "helps, but the systems and the US insurance process are what " +
      "postings actually check.",
    asks: [
      "An EHR or practice system: eClinicalWorks, Athena, Kareo, Epic",
      "US insurance verification, prior authorisation, billing and coding",
      "HIPAA awareness",
      "A nursing or allied-health degree for clinical support roles",
    ],
    blockers: [
      "A named EHR the applicant has not used",
      "Coding certification (CPC) required",
      "US-hours coverage for clinics",
    ],
  },
  teaching: {
    plural: "Teaching and tutoring",
    intro:
      "Teaching roles include online English teaching, subject tutoring and " +
      "corporate training. Online ESL work usually pays per class and needs " +
      "a quiet setup and early or late hours to fit students abroad.",
    asks: [
      "A TESOL or TEFL certificate for ESL work",
      "A degree in the subject for tutoring roles",
      "Headset, camera and a quiet space",
      "Class hours in the students' timezone",
    ],
    blockers: [
      "A certificate required and not held",
      "Native-speaker requirements on some platforms",
      "Class schedules outside the applicant's availability",
    ],
  },
  "data-analyst": {
    plural: "Data and analytics",
    intro:
      "Data roles run from reporting analysts to data engineers and " +
      "scientists. Most of these postings are specific about the tools, " +
      "and SQL plus one visualisation tool is the usual floor.",
    asks: [
      "SQL, stated with what it was used for",
      "Power BI, Tableau or Looker",
      "Python or R for analysis roles",
      "A warehouse or pipeline stack for engineering roles",
    ],
    blockers: [
      "No SQL on the resume",
      "Engineering roles asking for cloud data platforms",
      "Years at a level for senior roles",
    ],
  },
  "it-support": {
    plural: "IT support",
    intro:
      "IT support covers helpdesk and service desk roles, desktop support " +
      "and system or network administration. Remote helpdesk roles ask for " +
      "a ticketing tool and a shift; administration roles ask for the " +
      "platform, and often a certification.",
    asks: [
      "Ticketing: ServiceNow, Jira Service Management, Zendesk",
      "Microsoft 365, Active Directory, Intune",
      "Networking basics, or CCNA for network roles",
      "Shift availability for 24/7 coverage",
    ],
    blockers: [
      "A certification required (CCNA, CompTIA, Microsoft)",
      "Onsite support in a specific city",
      "A platform the whole role administers",
    ],
  },
};

export const ROLE_ORDER = Object.keys(ROLE_COPY);

export function copyFor(slug: string, name: string): RoleCopy {
  return (
    ROLE_COPY[slug] ?? {
      plural: name,
      intro: `Live ${name.toLowerCase()} postings open to people in the Philippines, checked every few hours.`,
      asks: [],
      blockers: [],
    }
  );
}
