# -*- coding: utf-8 -*-
"""
Scores live postings WITH their description text, which jobs.db does not keep.

Hits three of the fast JSON boards only - no Playwright, no scraping of HTML
pages. Read-only against JobHunt/sources.py.

    python live_check.py
"""
import os, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
JOBHUNT = r"D:\AIO Freelance\JobHunt"
sys.path.insert(0, JOBHUNT)

from profiles import from_jobhunt_profile
import profile as jh_profile
import sources
import matching as M

justin = from_jobhunt_profile(jh_profile)

rows = []
for name in ("remoteok", "remotive", "himalayas"):
    try:
        got = getattr(sources, name)()
        rows += got
        print("  %-12s %4d postings" % (name, len(got)))
    except Exception as e:
        print("  %-12s FAILED %s: %s" % (name, type(e).__name__, e))

body = [r for r in rows if (r.get("description") or "").strip()]
print("\n  %d postings, %d with description text (%.0f%%)"
      % (len(rows), len(body), 100.0 * len(body) / max(1, len(rows))))

res = M.score_many(rows, justin)
matches = [m for m in res if m.is_match]
near = [m for m in res if not m.is_match]

print("\n  excluded (not their profession) %4d" % (len(rows) - len(res)))
print("  matches                        %4d" % len(matches))
print("  near-misses                    %4d" % len(near))

print("\n  match tiers:")
for t in ("strong", "worth_a_look", "stretch"):
    print("    %-14s %3d" % (t, sum(1 for m in matches if m.tier == t)))

print("\n  blockers on near-misses:")
counts = {}
for m in near:
    for k in m.blocker_kinds:
        counts[k] = counts.get(k, 0) + 1
for k, n in sorted(counts.items(), key=lambda kv: -kv[1]):
    print("    %-14s %3d" % (k, n))

print("\n  TOP MATCHES")
for m in matches[:6]:
    print("    [%3d] %-44s %s" % (m.score, m.job["title"][:44], m.tier))
    print("          %s" % "; ".join(m.reasons[:2]))

print("\n  TOP NEAR-MISSES  (the 'came close' section)")
for m in sorted([m for m in near if m.showable],
                key=lambda m: -m.score)[:8]:
    print("    [%3d] %-44s %s" % (m.score, m.job["title"][:44],
                                  m.blockers[0].detail))

yrs = [M.parse_years_required((r.get("description") or "").lower())
       for r in body]
hit = [y for y in yrs if y is not None]
print("\n  years-requirement parsed on %d of %d bodies (%.0f%%)"
      % (len(hit), len(body), 100.0 * len(hit) / max(1, len(body))))
if hit:
    from collections import Counter
    print("  distribution:", dict(sorted(Counter(hit).items())))
