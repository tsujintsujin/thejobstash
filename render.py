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
import os, re, sys, html, shutil, subprocess, tempfile, datetime
from concurrent import futures

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
# one you act on, coral is the one you cannot. The fourth field is the label
# the dashboard puts on that section's box - Title Case because it is a
# control, not a heading, and it is here so the box and the section it opens
# can never drift apart.
#
# `stretch` is absent on purpose. Everything below profile.min_score is
# dropped in delivery.py rather than printed, so no section renders it and no
# box offers it. See that module's docstring.
SECTION_STYLE = {
    "strong":       (JADE,   "Strong matches",  "Apply to these first.", "Strong Matches"),
    "worth_a_look": (SUN,    "Worth a look",    "Solid fits with a caveat or two.", "Worth a Look"),
    "near_miss":    (CORAL,  "Came close",      "Real roles that matched your work but were blocked by one thing.", "Came Close"),
}
SECTION_ORDER = ("strong", "worth_a_look", "near_miss")

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
/* The heading and the download control share one lane. align-items is
   flex-start so a heading that wraps to two lines does not drag the button
   down with it. wrap keeps the button under the heading on a phone rather
   than squeezing both. */
.hero{display:flex;justify-content:space-between;align-items:flex-start;
      gap:18px;flex-wrap:wrap;margin-bottom:24px}
.hero .lede{margin-bottom:0}
.hero .dl{flex:0 0 auto}
.hero .dl a{display:inline-block;border:3px solid %(ink)s;background:%(flare)s;
     color:%(ink)s;font-size:13px;font-weight:800;padding:10px 18px;
     box-shadow:3px 3px 0 %(ink)s;text-decoration:none;text-transform:uppercase;
     letter-spacing:.06em;white-space:nowrap}
/* A print of this page must not show a button nobody can press. */
@media print{.hero .dl{display:none}}
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
        <h3><a href="%s" target="_blank" rel="noopener noreferrer">%s</a></h3>
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

    # A new tab, not this one. Somebody reads a digest of 58 roles and opens
    # several; sending them away from the list each time means going back for
    # every one. rel is not optional here: the href is a URL scraped off a job
    # board, and `allow-popups-to-escape-sandbox` means what opens is NOT
    # sandboxed - without noopener it could reach back through window.opener
    # and navigate the digest.
    bits.append('<div class="link">'
                '<a href="%s" target="_blank" rel="noopener noreferrer">'
                'Open the posting &rarr;</a>'
                '</div></div>' % _href(j.get("url")))
    return "".join(bits)


def digest_html(digest, email="", only=None, delivery_id=None):
    """One digest as a standalone page.

    `only` narrows it to a single section, which is what each box on the
    dashboard opens and what each part-PDF is printed from. The same function
    renders both so a box and the page behind it cannot say different things.
    `delivery_id` is what the download control points at; without it the page
    has no way back to the site and the control is left off.
    """
    s = digest["summary"]
    sec = digest["sections"]
    total = sum(len(sec[k]) for k in ("strong", "worth_a_look"))

    if only:
        heading = "%d %s." % (len(sec[only]), SECTION_STYLE[only][1].lower())
        lede = SECTION_STYLE[only][2]
    elif s["thin"]:
        heading = ("%d match%s, %d that came close."
                   % (total, "" if total == 1 else "es", len(sec["near_miss"])))
        lede = ("A quiet run. Rather than pad this out with roles that do not "
                "fit, here is everything that genuinely did - plus what came "
                "close and why.")
    else:
        heading = ("%d match%s, %d that came close."
                   % (total, "" if total == 1 else "es", len(sec["near_miss"])))
        lede = ("Scored against your resume, deduplicated across every board, "
                "and filtered down from %d live postings." % s["pool_size"])

    # Omitting `part` downloads the whole digest, which is the file the email
    # already attaches. A part view downloads only its own section.
    dl = ""
    if delivery_id:
        dl = ('<div class="dl"><a href="/api/download/%s%s">Download</a></div>'
              % (_esc(delivery_id), "?part=" + _esc(only) if only else ""))

    parts = ["""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TheJobStash &mdash; %s</title><style>%s</style></head><body>
<div class="bar"><div class="wrap">
  <div class="brand">TheJobStash</div>
  <div class="stamp">%s%s</div>
</div></div><div class="wrap">
<div class="hero"><div><h1>%s</h1>
<p class="lede">%s</p></div>%s</div>""" % (
        _esc(s["day"]), CSS, _esc(s["day"]),
        " &nbsp;·&nbsp; " + _esc(email) if email else "",
        _esc(heading), _esc(lede), dl)]

    for key in SECTION_ORDER:
        if only and key != only:
            continue
        rows = sec.get(key) or []
        if not rows:
            continue
        colour, title, blurb, _box = SECTION_STYLE[key]
        parts.append('<div class="sec"><div class="sechead" style="background:%s">'
                     '<h2>%s &mdash; %d</h2><em>%s</em></div>'
                     % (colour, title, len(rows), blurb))
        for m in rows:
            parts.append(_job_card(m, show_blockers=(key == "near_miss")))
        parts.append('</div>')

    # The blocker roll-up belongs to the came-close material. On a matches-only
    # part it is a list of walls next to jobs that cleared all of them.
    if s["blocker_copy"] and only in (None, "near_miss"):
        parts.append('<div class="block"><h2>What is standing in your way</h2>'
                     '<ul>%s</ul></div>'
                     % "".join("<li>%s</li>" % _esc(c) for c in s["blocker_copy"]))

    parts.append('<div class="foot">TheJobStash &middot; generated %s UTC '
                 '&middot; %d postings scored against your resume'
                 '</div></div></body></html>'
                 % (datetime.datetime.now(datetime.timezone.utc)
                    .strftime("%Y-%m-%d %H:%M"), s["scored"]))
    return "".join(parts)


def write_digest(digest, user_id, delivery_id, email="", out_dir=None):
    """Write the digest and print its PDFs. Returns (html, pdf|None, parts).

    Named by delivery id, never by date: a second run on the same date would
    otherwise overwrite the first run's files.

    Four files come out of one digest: the whole thing, which is what the
    email attaches and what the dashboard's View opens, plus one per section,
    which is what each box opens and downloads. `parts` describes the boxes in
    order - the site stores it and has no other way to know how many exist.

    The prints run concurrently. Each already gets a throwaway Chrome profile
    (see _print_pdf), which is the only thing that made them safe to overlap;
    sequentially this is four cold Chrome starts, about 19s, for no reason.
    """
    out_dir = out_dir or OUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_-]", "", user_id)[:24] or "user"
    dlv = re.sub(r"[^A-Za-z0-9_-]", "", delivery_id)[:32]
    base = os.path.join(out_dir, "digest-%s-%s" % (safe, dlv))

    sec = digest["sections"]
    parts = [k for k in SECTION_ORDER if sec.get(k)]

    html_path = base + ".html"
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(digest_html(digest, email, delivery_id=delivery_id))
    for key in parts:
        with open("%s-%s.html" % (base, key), "w", encoding="utf-8") as fh:
            fh.write(digest_html(digest, email, only=key,
                                 delivery_id=delivery_id))

    jobs = [(html_path, base + ".pdf")]
    jobs += [("%s-%s.html" % (base, k), "%s-%s.pdf" % (base, k)) for k in parts]
    with futures.ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        done = dict(zip([j[1] for j in jobs],
                        pool.map(lambda j: _print_pdf(*j), jobs)))

    manifest = [{"key": k, "count": len(sec[k]),
                 "label": SECTION_STYLE[k][3],
                 "colour": SECTION_STYLE[k][0],
                 "pdf": bool(done.get("%s-%s.pdf" % (base, k)))}
                for k in parts]
    return html_path, done.get(base + ".pdf"), manifest


def _print_pdf(html_path, pdf_path):
    """One headless-Chrome print. Returns the path, or None if it failed."""
    # Its own throwaway profile per render. Chrome locks a user-data-dir while
    # it holds it, so without this two runs printing at once - or one printing
    # while Justin's own Chrome is open - fight over the default profile and
    # one of them loses. The loss is silent, because the except below turns it
    # into "no PDF" rather than an error anyone sees.
    profile_dir = tempfile.mkdtemp(prefix="jobstash-chrome-")
    try:
        subprocess.run(
            [CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
             "--run-all-compositor-stages-before-draw",
             "--virtual-time-budget=4000",
             "--user-data-dir=" + profile_dir,
             "--print-to-pdf=" + pdf_path, "file:///" + html_path.replace("\\", "/")],
            check=True, timeout=90,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        # A missing Chrome must not cost the user their digest - the HTML is
        # the deliverable, the PDF is a convenience.
        pdf_path = None
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)
    return pdf_path


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
    empty = {"strong": [], "worth_a_look": [], "near_miss": [m]}
    out = digest_html({"sections": empty, "summary": {
        "day": "2026-01-01", "pool_size": 10, "scored": 10, "thin": False,
        "blocker_copy": []}})

    for kind, label in (("geography", "Location"), ("seniority", "Experience")):
        assert label in out, "blocker %s lost its name" % kind
    assert "Hiring only in the United States" in out, "blocker detail dropped"
    assert "Scanned" not in out, "the Scanned tile is back"
    assert "text-decoration:underline" not in CSS, "the posting link is a link again"
    assert INK in out and BONE in out and FLARE in out, "palette not applied"
    # javascript: in a scraped url must never reach an href
    assert _href("javascript:alert(1)") == "#"

    # A posting opens away from the digest, and never with a live opener
    # handle back to it. Counted rather than matched once: the title and the
    # button are both links to the same posting and both must carry it.
    assert out.count('target="_blank"') == 2, "a posting link lost target"
    assert out.count('rel="noopener noreferrer"') == 2, "a posting link lost rel"

    # -- the boxes ----------------------------------------------------------
    # Each box opens one section and downloads that section's PDF. The failure
    # this catches is silent in exactly the way the ones above are: a part
    # page that renders, looks right, and is quietly showing the wrong jobs or
    # pointing its download at the whole digest.
    j = lambda t: types.SimpleNamespace(
        job={"title": t, "company": "C", "location": "Remote",
             "source": "s", "salary": "", "url": "https://e.com/" + t,
             "description": "d"},
        score=40, reasons=[], blockers=[])
    d = {"sections": {"strong": [j("AlphaRole")],
                      "worth_a_look": [j("BetaRole")],
                      "near_miss": [m]},
         "summary": {"day": "2026-01-01", "pool_size": 10, "scored": 10,
                     "thin": False, "blocker_copy": ["3 were onsite only"]}}

    whole = digest_html(d, delivery_id="dlv_x")
    for t in ("AlphaRole", "BetaRole", "Senior React Developer"):
        assert t in whole, "%s missing from the whole digest" % t
    assert 'href="/api/download/dlv_x"' in whole, "whole digest lost Download"

    part = digest_html(d, only="strong", delivery_id="dlv_x")
    assert "AlphaRole" in part, "the strong part lost its own job"
    assert "BetaRole" not in part, "the strong part is showing other sections"
    assert 'href="/api/download/dlv_x?part=strong"' in part,         "a part's Download does not point at that part"
    assert "What is standing in your way" not in part,         "the blocker roll-up leaked onto a matches-only part"
    assert "What is standing in your way" in whole, "blocker roll-up lost"

    # The summary tiles are gone from every page. The heading already says
    # what the page holds, and a tile counting something else next to it read
    # as two numbers arguing - "58 worth a look." above a tile saying 81.
    assert 'class="tiles"' not in whole, "the tiles are back on the digest"
    assert 'class="tiles"' not in part, "the tiles are back on a part page"

    # No control without a route back to the site, rather than a dead button.
    assert "Download</a>" not in digest_html(d), "Download rendered with no id"

    # Every section with rows gets exactly one box, in order, and none of them
    # is `stretch` - that tier is dropped in delivery.py, never printed.
    assert [k for k in SECTION_ORDER if d["sections"].get(k)] ==         ["strong", "worth_a_look", "near_miss"], "box order changed"
    assert "stretch" not in SECTION_STYLE, "stretch is printable again"
    print("render.py selfcheck ok")


if __name__ == "__main__":
    _selfcheck()
