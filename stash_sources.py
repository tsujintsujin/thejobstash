# -*- coding: utf-8 -*-
"""
Keyword-free copies of the three Philippines boards from JobHunt/sources.py.

JobHunt's versions search developer keywords, because that file drives Justin's
own job hunt. TheJobStash serves whoever uploads a resume, so the pool has to
hold every profession before anybody asks. These page through each board
whole instead. JobHunt/sources.py stays untouched (CLAUDE.md non-negotiable 4);
the other ten boards take no keywords and are still imported from there.

Measured 2026-09-14:
  jobstreet   7,173 remote ads with no keyword, vs 715 for "developer"
  kalibrr       808 ads, all fields
  onlinejobs  any one listing stops at 300 rows (~9 hours of posts), so the
              unfiltered view plus the full/part-time/gig views are merged
"""
import re, urllib.parse

from sources import _get, _json, _strip, _row, UA    # shared, read-only


def kalibrr():
    out, seen = [], set()
    for offset in range(0, 5000, 50):                # 808 ads measured
        try:
            jobs = _json("https://www.kalibrr.com/kjs/job_board/search"
                         "?limit=50&text=&offset=%d" % offset).get("jobs", [])
        except Exception:
            break
        if not jobs:
            break
        for j in jobs:
            jid = j.get("id")
            if not jid or jid in seen:
                continue
            seen.add(jid)

            addr = ((j.get("google_location") or {}).get("address_components") or {})
            loc = ", ".join(x for x in (addr.get("city"), addr.get("region"),
                                        addr.get("country") or "Philippines") if x)
            if j.get("is_work_from_home"):
                loc += " (remote)"
            elif j.get("is_hybrid"):
                loc += " (hybrid)"

            lo, hi = j.get("base_salary"), j.get("maximum_salary")
            cur = j.get("salary_currency") or "PHP"
            sal = f"{cur} {lo} to {hi}" if lo else ""

            company = j.get("company") or {}
            ccode = company.get("code") or ""
            slug = j.get("slug") or ""
            link = (f"https://www.kalibrr.com/c/{ccode}/jobs/{jid}/{slug}"
                    if ccode and slug else f"https://www.kalibrr.com/job-board/{jid}")

            out.append(_row("kalibrr", j.get("name"),
                            j.get("company_name") or company.get("name"),
                            loc, link, j.get("description"),
                            (j.get("activation_date") or "")[:10], sal,
                            j.get("work_experience") or ""))
    return out


def onlinejobs():
    """The board hides the employer, so the job's own id stands in for it.
    ingest fingerprints on company + title; a constant company merged every
    "Virtual Assistant" from different employers into one row."""
    # ponytail: 4 views x 300 rows reaches ~1-2 days back. If a daily run
    # starts missing posts, split further by skill_tags.
    views = ("", "fullTime=on", "partTime=on", "gig=on")
    out, seen = [], set()
    for view in views:
        for offset in range(0, 300, 30):
            url = ("https://www.onlinejobs.ph/jobseekers/jobsearch"
                   + (f"/{offset}" if offset else "")
                   + ("?isFromJobsearchForm=1&" + view if view else ""))
            try:
                html_text = _get(url).decode("utf-8", "replace")
            except Exception:
                break

            blocks = html_text.split("<!-- Start -->")[1:]
            if not blocks:
                break
            for b in blocks:
                b = b.split("<!-- End -->")[0]
                m = re.search(r'href="(/jobseekers/job/[^"]+)"', b)
                t = re.search(r'<h4[^>]*>(.*?)</h4>', b, re.S)
                if not m or not t or m.group(1) in seen:
                    continue
                seen.add(m.group(1))
                jid = re.search(r"(\d+)$", m.group(1))
                title = _strip(re.sub(r"<span.*?</span>", " ", t.group(1), flags=re.S))
                posted = re.search(r'data-temp="(\d{4}-\d{2}-\d{2})', b)
                sal = re.search(r'<dd class="col">(.*?)</dd>', b, re.S)
                desc = re.search(r'<div class="desc[^"]*">(.*?)</div>', b, re.S)
                tags = re.findall(r"class='badge'>(.*?)</a>", b)
                body = _strip(desc.group(1)) if desc else ""
                if tags:
                    body += " " + " ".join(_strip(x) for x in tags)
                out.append(_row("onlinejobs", title,
                                "onlinejobs-" + (jid.group(1) if jid else m.group(1)),
                                "Philippines (remote)",
                                "https://www.onlinejobs.ph" + m.group(1),
                                body, posted.group(1) if posted else "",
                                _strip(sal.group(1)) if sal else ""))
    return out


def jobstreet(known=frozenset()):
    """Every remote ad on JobStreet PH. The search API only returns a teaser,
    so the full ad is fetched per job - but only for URLs not in `known`
    (ads already stored with a full description), so after the first runs
    each day only pays for its new ads."""
    from playwright.sync_api import sync_playwright

    # ponytail: ~0.6s per ad. 7,000 ads would be over an hour, so the first
    # runs backfill 1,500 a day instead. Raise it if a run has time to spare.
    DETAIL_CAP = 1500

    out, seen, budget = [], set(), DETAIL_CAP
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(user_agent=UA)
        try:
            page.goto("https://ph.jobstreet.com/jobs",
                      wait_until="domcontentloaded", timeout=45000)

            for pg in range(1, 200):                 # 72 pages measured
                try:
                    res = page.evaluate("""async (pg) => {
                        const u = '/api/jobsearch/v5/search?sitekey=PH-Main'
                                + '&sourcesystem=houston&pageSize=100'
                                + '&workarrangement=3&keywords=&page=' + pg;
                        const r = await fetch(u);
                        return r.ok ? await r.json() : null;
                    }""", pg)
                except Exception:
                    break
                rows = (res or {}).get("data") or []
                if not rows:
                    break

                for d in rows:
                    jid = str(d.get("id") or "")
                    arrange = ((d.get("workArrangements") or {}).get("displayText") or "")
                    if not jid or jid in seen or "remote" not in arrange.lower():
                        continue
                    seen.add(jid)

                    locs = d.get("locations") or []
                    loc = (locs[0].get("label") if locs else "") or "Philippines"
                    if "philippines" not in loc.lower():
                        loc += ", Philippines"
                    loc += " (remote)"

                    link = f"https://ph.jobstreet.com/job/{jid}"
                    body = " ".join(filter(None, [
                        d.get("teaser") or "",
                        " ".join(d.get("bulletPoints") or []),
                        " ".join(c.get("subclassification", {}).get("description", "")
                                 for c in (d.get("classifications") or [])),
                        " ".join(d.get("workTypes") or []),
                    ]))

                    if budget > 0 and link not in known:
                        try:
                            full = page.evaluate(r"""async (id) => {
                                const r = await fetch('/job/'+id, {headers:{'accept':'text/html'}});
                                if (!r.ok) return '';
                                const h = await r.text();
                                const m = h.match(/data-automation="jobAdDetails"[^>]*>([\s\S]{0,9000})/);
                                return m ? m[1] : '';
                            }""", jid)
                            if full:
                                body += " " + _strip(full)
                            budget -= 1
                        except Exception:
                            pass

                    out.append(_row("jobstreet", d.get("title") or "",
                                    d.get("companyName")
                                    or (d.get("advertiser") or {}).get("description"),
                                    loc, link, body,
                                    (d.get("listingDate") or "")[:10],
                                    d.get("salaryLabel") or ""))
        finally:
            browser.close()
    return out
