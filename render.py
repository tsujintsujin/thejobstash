# -*- coding: utf-8 -*-
"""
Digest -> standalone HTML, and HTML -> PDF via headless Chrome.

Chrome rather than WeasyPrint or reportlab because it is already on this
machine, JobHunt already prints its reports this way, and it renders the same
CSS the website uses - so the emailed PDF and the site cannot drift apart.

The styling is the Depo-derived system: thick black rules, hard offset shadows,
flat saturated blocks, one heavy grotesk. It has to survive being printed, so
nothing depends on hover, JavaScript or a web font that may not resolve.
"""
import os, re, sys, html, subprocess, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from summarise import summarise

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.environ.get("JOBSTASH_OUT", os.path.join(HERE, "outbox"))
CHROME = os.environ.get(
    "CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe")

# The site's tokens, copied from web/tailwind.config.ts. They are copied
# rather than imported because this file has to render with no site build and
# no network; if the palette there moves, move it here too. Ink is near-black
# so the accents are the only thing carrying hue, and every accent below is a
# background for ink text only - none of them holds white.
INK = "#16161C"     # borders, rules, body text
BONE = "#F5EFE3"    # the page ground
PAPER = "#FFFFFF"   # cards
AZURE = "#2B57EC"   # identity - the masthead, as on the site's hero
JADE = "#3ECFB4"    # positive - strong matches, score chips
SUN = "#F5B92E"     # attention - a caveat
CORAL = "#F0796A"   # quiet warm - blocked
FLARE = "#EE5130"   # action - the one thing on a card you press

# What each blocker kind is called on a card. `Blocker.detail` says what the
# role wanted; on its own that reads as a stray fact about the posting - "Hiring
# in Anywhere in the World [HQ: Sao Paulo]" - and never says which wall the
# reader just hit. The label is the wall; the detail is the evidence.
BLOCKER_LABEL = {
    "geography":     "Location",
    "seniority":     "Experience",
    "thin_skills":   "Skills",
    "authorisation": "Work authorisation",
    "onsite":        "Onsite only",
    "skill_gap":     "Different stack",
    "clearance":     "Security clearance",
    "off_field":     "Different field",
}

# Descending intensity, which is the whole point of the ordering: jade is the
# one you act on, coral is the one you cannot.
SECTION_STYLE = {
    "strong":       (JADE,   "Strong matches",  "Worth applying to today."),
    "worth_a_look": (SUN,    "Worth a look",    "Solid fits with a caveat or two."),
    "stretch":      (PAPER,  "Stretch",         "Below your usual bar - shown because the day was quiet."),
    "near_miss":    (CORAL,  "Came close",      "Real roles that matched your work but were blocked by one thing."),
}

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:%(bone)s;color:%(ink)s;font-family:"Inter",-apple-system,
     BlinkMacSystemFont,"Segoe UI","Helvetica Neue",Arial,sans-serif;
     -webkit-font-smoothing:antialiased;padding:0 0 48px}
.wrap{max-width:840px;margin:0 auto;padding:0 20px}
.bar{background:%(azure)s;border-bottom:3px solid %(ink)s;padding:26px 0;
     margin-bottom:26px}
.bar .wrap{display:flex;align-items:baseline;justify-content:space-between;
     gap:16px;flex-wrap:wrap}
.brand{font-size:26px;font-weight:800;letter-spacing:-.02em;color:%(bone)s}
.stamp{font-size:12px;font-weight:700;color:%(bone)s;opacity:.85;
     text-transform:uppercase;letter-spacing:.09em}
h1{font-size:34px;line-height:1.05;letter-spacing:-.03em;font-weight:800;
   margin:0 0 8px}
.lede{font-size:15px;line-height:1.5;max-width:62ch;margin-bottom:24px}
.tiles{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:30px}
.tile{flex:1 1 150px;border:3px solid %(ink)s;box-shadow:5px 5px 0 %(ink)s;
      padding:14px 16px;background:#fff}
.tile b{display:block;font-size:30px;font-weight:800;letter-spacing:-.02em;
        line-height:1}
.tile span{font-size:10px;font-weight:700;text-transform:uppercase;
           letter-spacing:.09em;opacity:.7}
.sec{margin:0 0 30px}
.sechead{border:3px solid %(ink)s;box-shadow:5px 5px 0 %(ink)s;padding:12px 16px;
         margin-bottom:16px;display:flex;justify-content:space-between;
         align-items:baseline;gap:12px;flex-wrap:wrap}
.sechead h2{font-size:19px;font-weight:800;letter-spacing:-.02em}
.sechead em{font-style:normal;font-size:12px;font-weight:600;opacity:.75}
.job{border:3px solid %(ink)s;background:#fff;padding:14px 16px;margin-bottom:11px;
     box-shadow:4px 4px 0 %(ink)s;page-break-inside:avoid}
.job .top{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}
.job h3{font-size:16px;font-weight:800;letter-spacing:-.01em;line-height:1.25}
.job h3 a{color:%(ink)s;text-decoration:none}
.score{border:2px solid %(ink)s;background:%(jade)s;font-size:12px;font-weight:800;
       padding:3px 9px;white-space:nowrap}
.meta{font-size:13px;font-weight:600;margin-top:5px}
.meta .co{font-weight:800}
.sub{font-size:12px;opacity:.72;margin-top:4px}
.why{margin-top:9px;border-left:4px solid %(ink)s;padding:5px 0 5px 10px;
     font-size:12.5px;font-weight:600}
.why h4{font-size:9.5px;font-weight:800;text-transform:uppercase;
        letter-spacing:.09em;opacity:.6;margin-bottom:6px}
.blk{font-size:12.5px;font-weight:600;line-height:1.45;padding:2px 0}
.blk b{display:inline-block;border:2px solid %(ink)s;background:%(sun)s;
       font-size:10px;font-weight:800;text-transform:uppercase;
       letter-spacing:.06em;padding:1px 6px;margin-right:7px;
       vertical-align:1px}
/* The site's .btn-sm: 3px ink border, flare ground, hard offset shadow, no
   underline. A digest is printed as often as it is clicked, so it wears the
   same box the dashboard does rather than a blue link. */
.link{margin-top:12px}
.link a{display:inline-block;border:3px solid %(ink)s;background:%(flare)s;
        color:%(ink)s;font-size:13px;font-weight:800;padding:9px 16px;
        box-shadow:3px 3px 0 %(ink)s;text-decoration:none}
.meta .sal{font-weight:700}
/* A literal middot, never the CSS hex-escape form. This block is an ordinary
   Python string, so Python reads that escape as octal - a NUL byte - followed
   by two stray characters, and every job line rendered the separator as a
   replacement glyph with "b7" printed after it. */
.meta .sal::before{content:" · ";opacity:.45}
.meta .sal.muted{opacity:.58;font-weight:600;font-style:italic}
.jsum{font-size:12.5px;line-height:1.55;margin-top:9px;opacity:.88}
.jlist{margin-top:11px}
.jlist h4{font-size:9.5px;font-weight:800;text-transform:uppercase;
          letter-spacing:.09em;opacity:.6;margin-bottom:5px}
.jlist ul{list-style:none}
.jlist li{font-size:12px;line-height:1.5;padding:3px 0 3px 13px;position:relative}
.jlist li::before{content:"";position:absolute;left:0;top:9px;width:5px;
                  height:5px;background:%(ink)s}
.block{background:%(ink)s;color:%(bone)s;border:3px solid %(ink)s;
       box-shadow:5px 5px 0 %(ink)s;padding:18px 20px;margin:30px 0}
.block h2{font-size:19px;font-weight:800;margin-bottom:10px}
.block ul{list-style:none}
.block li{font-size:14px;font-weight:600;padding:5px 0;
          border-bottom:1px solid rgba(245,239,227,.22)}
.block li:last-child{border-bottom:0}
.note{border:3px dashed %(ink)s;padding:14px 16px;font-size:13.5px;
      font-weight:600;margin-bottom:26px;background:#fff}
.foot{border-top:3px solid %(ink)s;margin-top:34px;padding-top:14px;
      font-size:11px;opacity:.65;font-weight:600}
@media print{body{background:#fff}
  .job,.tile,.sechead,.link a{box-shadow:none}}
""" % {"bone": BONE, "ink": INK, "azure": AZURE, "jade": JADE,
       "sun": SUN, "flare": FLARE}


def _esc(s):
    return html.escape(str(s or ""), quote=True)


def _href(u):
    """A job link, only if it is a web address.

    Escaping stops a URL breaking out of the attribute, but not a posting whose
    "URL" is javascript:... - that survives html.escape intact and runs when
    clicked. Scraped data does not get to pick the scheme.
    """
    u = str(u or "").strip()
    return _esc(u) if u.lower().startswith(("https://", "http://")) else "#"


def _job_card(m, show_blockers):
    """One job in the emailed digest.

    Carries the same detail the dashboard shows - salary, a summary, and
    whatever responsibilities and requirements could be recovered from the
    posting - because the email is the product and a bare title is not enough
    to decide whether to apply. Every section is conditional: extraction from
    scraped prose succeeds on roughly 60% of postings.
    """
    j = m.job
    d = summarise(j.get("description"), j.get("salary"))

    sal_class = "sal" if d["salary_known"] else "sal muted"
    bits = ["""
    <div class="job">
      <div class="top">
        <h3><a href="%s">%s</a></h3>
        <span class="score">%d</span>
      </div>
      <div class="meta"><span class="co">%s</span>
        <span class="%s">%s</span></div>
      <div class="sub">%s &nbsp;&middot;&nbsp; via %s</div>""" % (
        _href(j.get("url")), _esc(j.get("title")), m.score,
        _esc(j.get("company") or "Unknown company"),
        sal_class, _esc(d["salary"]),
        _esc(j.get("location") or "Location not stated"),
        _esc(j.get("source")))]

    # A near-miss is the section the product exists for, so every blocker is
    # named and evidenced rather than summarised into one semicolon-joined run.
    if show_blockers and m.blockers:
        bits.append('<div class="why"><h4>What blocked it</h4>%s</div>'
                    % "".join(
                        '<div class="blk"><b>%s</b>%s</div>'
                        % (_esc(BLOCKER_LABEL.get(b.kind,
                                                  b.kind.replace("_", " "))),
                           _esc(b.detail))
                        for b in m.blockers))
    else:
        why = "; ".join(_esc(r) for r in m.reasons[:2])
        bits.append('<div class="why">%s</div>' % (why or "&nbsp;"))

    if d["summary"]:
        bits.append('<p class="jsum">%s</p>' % _esc(d["summary"]))

    for heading, items in (("What you&rsquo;d be doing", d["responsibilities"]),
                           ("What they&rsquo;re asking for", d["requirements"])):
        if items:
            bits.append('<div class="jlist"><h4>%s</h4><ul>%s</ul></div>'
                        % (heading,
                           "".join("<li>%s</li>" % _esc(i) for i in items)))

    bits.append('<div class="link"><a href="%s">Open the posting &rarr;</a>'
                '</div></div>' % _href(j.get("url")))
    return "".join(bits)


def digest_html(digest, email=""):
    s = digest["summary"]
    sec = digest["sections"]
    total = sum(len(sec[k]) for k in ("strong", "worth_a_look", "stretch"))

    if s["first_ever"]:
        lede = ("This is your first sweep, so it reaches back over everything "
                "still live. From here each run brings what is new, and "
                "nothing you have already seen.")
    elif s["thin"]:
        lede = ("A quiet run. Rather than pad this out with roles that do not "
                "fit, here is everything that genuinely did - plus what came "
                "close and why.")
    else:
        lede = ("Scored against your resume, deduplicated across every board, "
                "and filtered down from %d live postings." % s["pool_size"])

    parts = ["""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TheJobStash &mdash; %s</title><style>%s</style></head><body>
<div class="bar"><div class="wrap">
  <div class="brand">TheJobStash</div>
  <div class="stamp">%s%s</div>
</div></div><div class="wrap">
<h1>%d match%s, %d that came close.</h1>
<p class="lede">%s</p>
<div class="tiles">
  <div class="tile"><b>%d</b><span>Matches</span></div>
  <div class="tile" style="background:%s"><b>%d</b><span>Strong</span></div>
  <div class="tile"><b>%d</b><span>Came close</span></div>
</div>""" % (_esc(s["day"]), CSS, _esc(s["day"]),
             " &nbsp;·&nbsp; " + _esc(email) if email else "",
             total, "" if total == 1 else "es", len(sec["near_miss"]),
             lede, total, JADE, len(sec["strong"]),
             len(sec["near_miss"]))]

    if s["backfilled"]:
        parts.append('<div class="note">%d of these were held back from '
                     'earlier sweeps so today would not come up short. '
                     '%d still in reserve.</div>'
                     % (s["backfilled"], s["reserve_left"]))

    for key in ("strong", "worth_a_look", "stretch", "near_miss"):
        rows = sec.get(key) or []
        if not rows:
            continue
        colour, title, blurb = SECTION_STYLE[key]
        parts.append('<div class="sec"><div class="sechead" style="background:%s">'
                     '<h2>%s &mdash; %d</h2><em>%s</em></div>'
                     % (colour, title, len(rows), blurb))
        for m in rows:
            parts.append(_job_card(m, show_blockers=(key == "near_miss")))
        parts.append('</div>')

    if s["blocker_copy"]:
        parts.append('<div class="block"><h2>What is standing in your way</h2>'
                     '<ul>%s</ul></div>'
                     % "".join("<li>%s</li>" % _esc(c) for c in s["blocker_copy"]))

    parts.append('<div class="foot">TheJobStash &middot; generated %s UTC '
                 '&middot; %d postings scored against your resume'
                 '</div></div></body></html>'
                 % (datetime.datetime.now(datetime.timezone.utc)
                    .strftime("%Y-%m-%d %H:%M"), s["scored"]))
    return "".join(parts)


def write_digest(digest, user_id, email="", out_dir=None):
    """Write the HTML and print a PDF beside it. Returns (html, pdf|None)."""
    out_dir = out_dir or OUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    stamp = digest["summary"]["day"]
    safe = re.sub(r"[^A-Za-z0-9_-]", "", user_id)[:24] or "user"
    base = os.path.join(out_dir, "digest-%s-%s" % (safe, stamp))

    html_path = base + ".html"
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(digest_html(digest, email))

    pdf_path = base + ".pdf"
    try:
        subprocess.run(
            [CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
             "--run-all-compositor-stages-before-draw",
             "--virtual-time-budget=4000",
             "--print-to-pdf=" + pdf_path, "file:///" + html_path.replace("\\", "/")],
            check=True, timeout=90,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        # A missing Chrome must not cost the user their digest - the HTML is
        # the deliverable, the PDF is a convenience.
        pdf_path = None
    return html_path, pdf_path


def _selfcheck():
    """`python render.py` - the template still says what it is meant to say.

    Cheap because the failure it catches is silent: a card that renders, looks
    fine, and has quietly stopped naming the blocker or lost its button.
    """
    import types
    B = lambda k, d: types.SimpleNamespace(kind=k, detail=d)
    m = types.SimpleNamespace(
        job={"title": "Senior React Developer", "company": "Northbeam",
             "location": "Austin, TX", "source": "remoteok", "salary": "",
             "url": "https://example.com/j", "description": "React and Node."},
        score=62, reasons=["strong skill overlap"],
        blockers=[B("geography", "Hiring only in the United States"),
                  B("seniority", "Wants 8+ years")])
    empty = {"strong": [], "worth_a_look": [], "stretch": [], "near_miss": [m]}
    out = digest_html({"sections": empty, "summary": {
        "day": "2026-01-01", "pool_size": 10, "scored": 10, "backfilled": 0,
        "reserve_left": 0, "first_ever": False, "thin": False,
        "blocker_copy": []}})

    for kind, label in (("geography", "Location"), ("seniority", "Experience")):
        assert label in out, "blocker %s lost its name" % kind
    assert "Hiring only in the United States" in out, "blocker detail dropped"
    assert "Scanned" not in out, "the Scanned tile is back"
    assert "text-decoration:underline" not in CSS, "the posting link is a link again"
    assert INK in out and BONE in out and FLARE in out, "palette not applied"
    # javascript: in a scraped url must never reach an href
    assert _href("javascript:alert(1)") == "#"
    print("render.py selfcheck ok")


if __name__ == "__main__":
    _selfcheck()
