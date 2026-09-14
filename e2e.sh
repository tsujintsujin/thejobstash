#!/usr/bin/env bash
# End-to-end walk of the real site over HTTP: signup, resume upload, preview,
# delivery, download. Exercises every route a user touches.
#
#   bash e2e.sh [base-url]
set -u
BASE="${1:-http://localhost:3200}"
JAR=$(mktemp)
EMAIL="e2e-$(date +%s)@demo.test"
RESUME="D:/AIO Freelance/Resumes/Justin Masiga - Full CV.pdf"
PASS=0; FAIL=0

ok()   { PASS=$((PASS+1)); printf '  \033[32mPASS\033[0m %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  \033[31mFAIL\033[0m %s — %s\n' "$1" "$2"; }
code() { curl -s -o /dev/null -w '%{http_code}' -b "$JAR" -c "$JAR" "$@"; }

echo "== TheJobStash e2e =="
echo "   base  $BASE"
echo "   user  $EMAIL"
echo

# --- public pages ---------------------------------------------------------
for p in / /signup "/signup?mode=signin"; do
  c=$(code "$BASE$p")
  [ "$c" = "200" ] && ok "GET $p" || bad "GET $p" "HTTP $c"
done

# Signing in and signing up are one card at /signup now. /login is kept only
# as a redirect, because the address is in the wild - so 307 is the pass here,
# and a 200 would mean the old duplicate page came back.
c=$(code "$BASE/login")
[ "$c" = "307" ] && ok "GET /login redirects to the auth card"   || bad "GET /login redirects to the auth card" "HTTP $c"

# The landing page must show live pool numbers, not a placeholder.
body=$(curl -s "$BASE/")
echo "$body" | grep -q "Live postings" && ok "landing renders live stats" \
  || bad "landing renders live stats" "marker missing"
pool=$(echo "$body" | grep -oE '[0-9,]+</b><span>Live postings' | grep -oE '^[0-9,]+')
[ -n "$pool" ] && ok "pool count on page: $pool" || bad "pool count" "not found"

# --- auth gate ------------------------------------------------------------
c=$(code "$BASE/dashboard")
[ "$c" = "307" ] || [ "$c" = "302" ] && ok "dashboard redirects when signed out" \
  || bad "dashboard redirect" "HTTP $c"

c=$(code -X POST "$BASE/api/deliver")
[ "$c" = "401" ] && ok "deliver refuses anonymous" || bad "deliver anon" "HTTP $c"

# --- signup ---------------------------------------------------------------
r=$(curl -s -b "$JAR" -c "$JAR" -X POST "$BASE/api/auth/signup" \
      -H 'Content-Type: application/json' \
      -d "{\"email\":\"$EMAIL\",\"password\":\"testing1234\"}")
echo "$r" | grep -q '"ok":true' && ok "signup" || bad "signup" "$r"

c=$(code "$BASE/dashboard")
[ "$c" = "200" ] && ok "dashboard reachable after signup" \
  || bad "dashboard after signup" "HTTP $c"

# duplicate email must be refused
r=$(curl -s -X POST "$BASE/api/auth/signup" -H 'Content-Type: application/json' \
      -d "{\"email\":\"$EMAIL\",\"password\":\"testing1234\"}")
echo "$r" | grep -q 'already' && ok "duplicate email refused" \
  || bad "duplicate email" "$r"

# weak password must be refused
r=$(curl -s -X POST "$BASE/api/auth/signup" -H 'Content-Type: application/json' \
      -d '{"email":"weak@demo.test","password":"123"}')
echo "$r" | grep -q '8 characters' && ok "weak password refused" \
  || bad "weak password" "$r"

# --- deliver before a resume exists ---------------------------------------
r=$(curl -s -b "$JAR" -c "$JAR" -X POST "$BASE/api/deliver")
echo "$r" | grep -q 'Upload a resume' && ok "deliver blocked without resume" \
  || bad "deliver without resume" "$r"

# --- resume upload --------------------------------------------------------
if [ ! -f "$RESUME" ]; then
  bad "resume upload" "test resume not found at $RESUME"
else
  r=$(curl -s -b "$JAR" -c "$JAR" -X POST "$BASE/api/resume" \
        -F "resume=@$RESUME;type=application/pdf")
  echo "$r" | grep -q '"ok":true' && ok "resume upload + parse" \
    || bad "resume upload" "$(echo "$r" | head -c 200)"
  yrs=$(echo "$r" | grep -oE '"years": ?[0-9]+' | grep -oE '[0-9]+$')
  # "level" appears in both diagnostics and profile - take the first.
  lvl=$(echo "$r" | grep -oE '"level": ?"[a-z]+"' | head -1 | grep -oE '[a-z]+"$' | tr -d '"')
  [ "$yrs" = "3" ] && ok "parsed years = 3 (relevant, not total)" \
    || bad "parsed years" "got '$yrs', expected 3"
  [ "$lvl" = "mid" ] && ok "parsed level = mid" || bad "parsed level" "got '$lvl'"
fi

# rejects a file type it cannot read
echo "not a resume" > /tmp/jobstash-e2e.exe 2>/dev/null || echo "x" > ./jobstash-e2e.exe
BADF=$( [ -f /tmp/jobstash-e2e.exe ] && echo /tmp/jobstash-e2e.exe || echo ./jobstash-e2e.exe )
r=$(curl -s -b "$JAR" -c "$JAR" -X POST "$BASE/api/resume" -F "resume=@$BADF")
echo "$r" | grep -q 'we can read\|We can read' && ok "rejects unsupported file type" \
  || bad "unsupported file type" "$r"
rm -f "$BADF"

# --- preview (must not consume) -------------------------------------------
r=$(curl -s -b "$JAR" -c "$JAR" -X POST "$BASE/api/deliver?preview=1")
echo "$r" | grep -q '"ok":true' && ok "preview scores" \
  || bad "preview" "$(echo "$r" | head -c 200)"
m1=$(echo "$r" | grep -oE '"matches": ?[0-9]+' | head -1 | grep -oE '[0-9]+$')
n1=$(echo "$r" | grep -oE '"near_misses": ?[0-9]+' | head -1 | grep -oE '[0-9]+$')
echo "         preview: $m1 matches, $n1 near-misses"

r2=$(curl -s -b "$JAR" -c "$JAR" -X POST "$BASE/api/deliver?preview=1")
m2=$(echo "$r2" | grep -oE '"matches": ?[0-9]+' | head -1 | grep -oE '[0-9]+$')
[ "$m1" = "$m2" ] && ok "preview is idempotent (consumed nothing)" \
  || bad "preview idempotent" "$m1 then $m2"

# --- real delivery --------------------------------------------------------
r=$(curl -s -b "$JAR" -c "$JAR" -X POST "$BASE/api/deliver")
echo "$r" | grep -q '"ok":true' && ok "delivery runs" \
  || bad "delivery" "$(echo "$r" | head -c 200)"
echo "$r" | grep -q '"email_status": *"outbox"' && ok "email written to outbox" \
  || bad "email outbox" "no outbox status"

# After delivering, the same jobs must not come back.
#
# This used to assert the second preview returned FEWER jobs. That only held
# while the pool was thin: with 1,760 rows the sweep refills to the daily cap
# with different postings, so a healthy pipeline failed the test. The real
# invariant is that the two sets are disjoint - no delivered URL reappears.
r3=$(curl -s -b "$JAR" -c "$JAR" -X POST "$BASE/api/deliver?preview=1")
m3=$(echo "$r3" | grep -oE '"matches": ?[0-9]+' | head -1 | grep -oE '[0-9]+$')
echo "$r"  | grep -oE 'https?://[^"]+' | sort -u > sent.urls.tmp
echo "$r3" | grep -oE 'https?://[^"]+' | sort -u > again.urls.tmp
dupes=$(comm -12 sent.urls.tmp again.urls.tmp | wc -l | tr -d ' ')
rm -f sent.urls.tmp again.urls.tmp
if [ "${dupes:-1}" -eq 0 ]; then
  ok "delivered jobs no longer reappear (0 of ${m3:-0} were sent before)"
else
  bad "sent_jobs dedupe" "$dupes delivered URLs came back"
fi

# --- download -------------------------------------------------------------
DLID=$(curl -s -b "$JAR" -c "$JAR" "$BASE/dashboard" \
       | grep -oE '/api/download/dlv_[a-f0-9]+' | head -1)
if [ -n "$DLID" ]; then
  c=$(code "$BASE$DLID")
  [ "$c" = "200" ] && ok "PDF download" || bad "PDF download" "HTTP $c"
  ct=$(curl -s -b "$JAR" -c "$JAR" -o /dev/null -w '%{content_type}' "$BASE$DLID")
  echo "$ct" | grep -q pdf && ok "download is a PDF ($ct)" || bad "content type" "$ct"
  c=$(curl -s -o /dev/null -w '%{http_code}' "$BASE$DLID")   # no cookie jar
  [ "$c" = "401" ] && ok "download refuses anonymous" || bad "download anon" "HTTP $c"
else
  bad "download link" "no delivery link on dashboard"
fi

# --- logout ---------------------------------------------------------------
curl -s -b "$JAR" -c "$JAR" -X POST "$BASE/api/auth/logout" -o /dev/null
c=$(code "$BASE/dashboard")
[ "$c" = "307" ] || [ "$c" = "302" ] && ok "logout ends the session" \
  || bad "logout" "HTTP $c"

rm -f "$JAR"
echo
echo "== $PASS passed, $FAIL failed =="
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
