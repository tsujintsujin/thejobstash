# HANDOFF-SEO — what the site targets in search, and why

2026-09-18. Read before renaming a `/jobs/<slug>`, changing the home title,
or adding a role family.

## What people in the Philippines actually type

Taken from Google's own autocomplete with `gl=ph` (Bing's keyword tool had no
data for a days-old site). The head terms and the modifiers people bolt on:

| Head term | Modifiers seen most |
|---|---|
| online jobs (philippines) | home based, part time, no experience, for students, legit, non voice |
| work from home jobs philippines | no experience, non voice, part time, hiring |
| remote jobs philippines | no experience, part time, non voice, entry level |
| job sites philippines | best, legit, reddit |
| virtual assistant jobs | philippines, no experience, part time, for beginners |

"job site" and "online jobs" on their own are owned by the big boards and by
a brand literally named after the phrase. A new domain does not take those by
editing copy; it takes the long tail first and earns the head terms with links.

## What each page is aimed at

| Page | Title / H1 | Aimed at |
|---|---|---|
| `/` | Online jobs in the Philippines, matched to your resume | online jobs philippines, jobs that match my resume |
| `/jobs` | Job openings in the Philippines by role | job openings / job hiring philippines |
| `/jobs/remote` | Online and work-from-home jobs in the Philippines | work from home / home based / online jobs philippines. Slug kept as `remote` so already-crawled URLs do not move |
| `/jobs/part-time` | Part-time jobs in the Philippines | part time online jobs, online jobs for students |
| `/jobs/no-experience` | Entry-level and no-experience jobs in the Philippines | wfh / online jobs no experience, fresh graduates |
| `/jobs/non-voice` | Non-voice jobs in the Philippines | non voice wfh, chat support |
| other `/jobs/<slug>` | `<Role> jobs in the Philippines` | `<role> jobs philippines` |
| home FAQ "Are these jobs legit?" | FAQPage JSON-LD | legit online jobs philippines |

Part-time, no-experience and non-voice are matched on the posting's text as
well as its title (`pool_pages._DESC`), because titles rarely say it. A senior
title or "not an entry-level position" keeps a posting off the no-experience
page (`_NOT_TITLE`, `_NOT_DESC`). `python pool_pages.py --test` covers both.

Rule 8 of `CLAUDE.md` still binds all of this: no board names or board count
in any title, description, FAQ or `llms.txt`. That is why there is no
"best job sites in the Philippines" comparison page, the one piece of content
that would target that search directly.

## Consoles

- Google Search Console: domain property `sc-domain:thejobstash.com`,
  verified by DNS TXT. Sitemap submitted 2026-09-18. Home re-indexing
  requested 2026-09-18; the last crawl before that was 2026-09-15, which is
  why the result still showed the old snippet and a blank favicon.
- Bing Webmaster Tools: imported from Search Console; sitemap submitted
  2026-09-18.

## What only Justin can do

Links from other sites decide the broad terms. Candidates: the TheJobStash
Facebook page, LinkedIn, r/buhaydigital and r/phcareers (answer questions,
do not spam), Filipino freelancer and job groups, Product Hunt. A post there
that links to a specific `/jobs/<slug>` page is worth more than one to the
home page.
