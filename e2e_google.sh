#!/usr/bin/env bash
# End-to-end walk of Google sign-in against a local stand-in for Google.
#
#   bash e2e_google.sh [base-url] [stub-port]
#
# The Next server must already be running with sign-in pointed at the stub:
#
#   JOBSTASH_GOOGLE_CLIENT_ID=stub-id \
#   JOBSTASH_GOOGLE_CLIENT_SECRET=stub-secret \
#   JOBSTASH_GOOGLE_STUB_ORIGIN=http://localhost:3210 \
#   npm run dev
#
# This script owns the stub itself and starts and stops it. It refuses to run
# against a server that is not stub-wired, because every check below would
# then be passing for the wrong reason.
set -u
BASE="${1:-http://localhost:3200}"
STUB_PORT="${2:-3210}"
STUB="http://localhost:$STUB_PORT"
HERE="$(cd "$(dirname "$0")" && pwd)"
PASS=0; FAIL=0
STAMP=$(date +%s)

ok()  { PASS=$((PASS+1)); printf '  \033[32mPASS\033[0m %s\n' "$1"; }
bad() { FAIL=$((FAIL+1)); printf '  \033[31mFAIL\033[0m %s - %s\n' "$1" "$2"; }

echo "== TheJobStash - Google sign-in e2e =="
echo "   base  $BASE"
echo "   stub  $STUB"
echo

# --- stub lifecycle -------------------------------------------------------
node "$HERE/web/test/google_stub.mjs" "$STUB_PORT" >/tmp/jobstash_stub.log 2>&1 &
STUB_PID=$!
cleanup() { kill "$STUB_PID" 2>/dev/null; }
trap cleanup EXIT
for _ in 1 2 3 4 5 6 7 8 9 10; do
  curl -s -o /dev/null -X POST "$STUB/_identity" -d '{}' && break
  sleep 0.3
done

# --- the server must actually be pointed at the stub ----------------------
start=$(curl -s -o /dev/null -w '%{redirect_url}' "$BASE/api/auth/google")
case "$start" in
  "$STUB"/*) ok "server is wired to the stub, not the real Google" ;;
  *accounts.google.com*)
    bad "server is wired to the stub" "it points at the real Google - set JOBSTASH_GOOGLE_STUB_ORIGIN and restart"
    echo; echo "aborting: every check below would pass for the wrong reason."; exit 1 ;;
  *)
    bad "server is wired to the stub" "GET /api/auth/google did not redirect (Google creds unset?)"
    echo; echo "aborting: every check below would pass for the wrong reason."; exit 1 ;;
esac

# Set the identity the stub will present on the next sign-in.
be() { curl -s -o /dev/null -X POST "$STUB/_identity" -H 'Content-Type: application/json' -d "$1"; }

# Run one whole sign-in with a fresh cookie jar; echo the URL it ended on.
#   $1 identity json   $2 jar   $3 optional ?next= value
signin() {
  local q=""
  [ -n "${3:-}" ] && q="?next=$3"
  be "$1"
  curl -s -L -o /dev/null -b "$2" -c "$2" -w '%{url_effective}' "$BASE/api/auth/google$q"
}

# ==========================================================================
echo "-- starting the flow"

JAR=$(mktemp)
hdrs=$(curl -s -D - -o /dev/null -c "$JAR" "$BASE/api/auth/google")
echo "$hdrs" | grep -qi 'jobstash_oauth=' \
  && ok "state cookie is set before leaving" || bad "state cookie" "not in response"
echo "$hdrs" | grep -qi 'jobstash_oauth=.*httponly' \
  && ok "state cookie is httpOnly" || bad "state cookie httpOnly" "flag missing"
echo "$hdrs" | grep -qi 'jobstash_oauth=.*samesite=lax' \
  && ok "state cookie is SameSite=Lax (survives the bounce back)" \
  || bad "state cookie SameSite" "not lax"
echo "$hdrs" | grep -qi 'prompt=select_account' \
  && ok "asks Google to choose an account, never silently reuses one" \
  || bad "prompt=select_account" "missing from the authorize URL"

# ==========================================================================
echo "-- a brand new person"

NEW_EMAIL="gnew-$STAMP@demo.test"
JAR=$(mktemp)
end=$(signin "{\"sub\":\"sub-new-$STAMP\",\"email\":\"$NEW_EMAIL\",\"email_verified\":true}" "$JAR")
case "$end" in
  */upload) ok "a new account lands on /upload, not a dashboard with nothing in it" ;;
  *) bad "new account lands on /upload" "ended on $end" ;;
esac

c=$(curl -s -o /dev/null -w '%{http_code}' -b "$JAR" "$BASE/dashboard")
[ "$c" = "200" ] && ok "the session works - /dashboard renders" || bad "session after signup" "HTTP $c"
curl -s -b "$JAR" "$BASE/dashboard" | grep -q "$NEW_EMAIL" \
  && ok "the dashboard is that person's, by email" || bad "dashboard identity" "email not on page"

# The account is OAuth-only, so it has no password to guess.
r=$(curl -s -X POST "$BASE/api/auth/login" -H 'Content-Type: application/json' \
      -d "{\"email\":\"$NEW_EMAIL\",\"password\":\"\"}")
echo "$r" | grep -q '"error"' \
  && ok "a Google-only account refuses an empty password" || bad "empty password refused" "$r"

# ==========================================================================
echo "-- the same person coming back"

JAR=$(mktemp)
end=$(signin "{\"sub\":\"sub-new-$STAMP\",\"email\":\"$NEW_EMAIL\",\"email_verified\":true}" "$JAR")
case "$end" in
  */dashboard) ok "a returning person goes to the dashboard, not back to /upload" ;;
  *) bad "returning person to /dashboard" "ended on $end" ;;
esac

# Changing the Google address must not create a second stash: the subject id
# is the identity, and Google lets people change their email.
JAR=$(mktemp)
end=$(signin "{\"sub\":\"sub-new-$STAMP\",\"email\":\"moved-$STAMP@demo.test\",\"email_verified\":true}" "$JAR")
curl -s -b "$JAR" "$BASE/dashboard" | grep -q "$NEW_EMAIL" \
  && ok "a changed Google address still reaches the original account" \
  || bad "identity is the subject id, not the email" "landed somewhere else"

# ==========================================================================
echo "-- where it sends you afterwards"

JAR=$(mktemp)
end=$(signin "{\"sub\":\"sub-new-$STAMP\",\"email\":\"$NEW_EMAIL\",\"email_verified\":true}" "$JAR" "/upload")
case "$end" in */upload) ok "an internal ?next is honoured" ;; *) bad "?next honoured" "ended on $end" ;; esac

JAR=$(mktemp)
end=$(signin "{\"sub\":\"sub-new-$STAMP\",\"email\":\"$NEW_EMAIL\",\"email_verified\":true}" "$JAR" "https://evil.test/harvest")
case "$end" in
  "$BASE"/dashboard) ok "an off-site ?next is refused - no open redirect" ;;
  *evil.test*) bad "open redirect" "IT FOLLOWED $end" ;;
  *) bad "off-site ?next refused" "ended on $end" ;;
esac

JAR=$(mktemp)
end=$(signin "{\"sub\":\"sub-new-$STAMP\",\"email\":\"$NEW_EMAIL\",\"email_verified\":true}" "$JAR" "//evil.test/harvest")
case "$end" in
  *evil.test*) bad "protocol-relative ?next refused" "IT FOLLOWED $end" ;;
  *) ok "a protocol-relative //evil.test ?next is refused" ;;
esac

# The destination rides in the same cookie as the state, separated by a colon.
# A path containing its own colon used to be cut short there.
JAR=$(mktemp)
end=$(signin "{\"sub\":\"sub-new-$STAMP\",\"email\":\"$NEW_EMAIL\",\"email_verified\":true}" "$JAR" "/dashboard?tab=a:b")
case "$end" in
  *"a:b"*) ok "a ?next containing a colon survives the round trip" ;;
  *) bad "colon in ?next survives" "truncated to $end" ;;
esac

# ==========================================================================
echo "-- meeting an account that already exists"

PW_EMAIL="gpw-$STAMP@demo.test"
r=$(curl -s -X POST "$BASE/api/auth/signup" -H 'Content-Type: application/json' \
      -d "{\"email\":\"$PW_EMAIL\",\"password\":\"testing1234\"}")
echo "$r" | grep -q '"ok":true' && ok "made a password account to collide with" || bad "setup password account" "$r"

# Unverified: Google is not asserting this person owns the address, so linking
# would hand over someone else's stash to whoever set it.
JAR=$(mktemp)
end=$(signin "{\"sub\":\"sub-unver-$STAMP\",\"email\":\"$PW_EMAIL\",\"email_verified\":false}" "$JAR")
case "$end" in
  *err=*) ok "an UNVERIFIED Google email will not claim an existing account" ;;
  *) bad "unverified email refused" "ended on $end - it may have linked" ;;
esac
c=$(curl -s -o /dev/null -w '%{http_code}' -b "$JAR" "$BASE/dashboard")
[ "$c" != "200" ] && ok "and no session was handed out on that refusal" \
  || bad "no session on refusal" "the dashboard rendered"

# Verified: Google vouches for the address, so the two are the same person.
JAR=$(mktemp)
end=$(signin "{\"sub\":\"sub-ver-$STAMP\",\"email\":\"$PW_EMAIL\",\"email_verified\":true}" "$JAR")
case "$end" in
  */dashboard) ok "a VERIFIED Google email links to the existing account" ;;
  *) bad "verified email links" "ended on $end" ;;
esac
curl -s -b "$JAR" "$BASE/dashboard" | grep -q "$PW_EMAIL" \
  && ok "and it is the same account, not a duplicate" || bad "linked to same account" "different email on page"

# Linking must not cost them their password.
r=$(curl -s -X POST "$BASE/api/auth/login" -H 'Content-Type: application/json' \
      -d "{\"email\":\"$PW_EMAIL\",\"password\":\"testing1234\"}")
echo "$r" | grep -q '"ok":true' \
  && ok "the password still works after linking Google" || bad "password survives linking" "$r"

# ==========================================================================
echo "-- things going wrong"

# A forged callback URL: the state does not match the cookie. This is the
# check that stops someone being landed inside an attacker's account.
JAR=$(mktemp)
end=$(signin "{\"sub\":\"sub-forge-$STAMP\",\"email\":\"forge-$STAMP@demo.test\",\"email_verified\":true,\"forgeState\":\"wrong-state\"}" "$JAR")
case "$end" in
  *err=*) ok "a mismatched state is rejected (CSRF on the login itself)" ;;
  *) bad "state mismatch rejected" "ended on $end - IT SIGNED IN" ;;
esac
c=$(curl -s -o /dev/null -w '%{http_code}' -b "$JAR" "$BASE/dashboard")
[ "$c" != "200" ] && ok "and no session came out of it" || bad "no session on state mismatch" "dashboard rendered"

# A callback with no state cookie at all - a stale tab, or a link sent cold.
JAR=$(mktemp)
end=$(curl -s -L -o /dev/null -b "$JAR" -c "$JAR" -w '%{url_effective}' \
      "$BASE/api/auth/google/callback?code=x&state=y")
case "$end" in
  *err=*) ok "a callback with no state cookie is rejected" ;;
  *) bad "no-cookie callback rejected" "ended on $end" ;;
esac

# Pressing Cancel on Google's screen is not an error worth shouting about.
JAR=$(mktemp)
end=$(signin "{\"deny\":true}" "$JAR")
case "$end" in
  *err=*) bad "cancel is quiet" "it shouted: $end" ;;
  *signup*) ok "pressing Cancel returns quietly to the card, with no error" ;;
  *) bad "cancel returns to the card" "ended on $end" ;;
esac

# Google declining the token exchange.
JAR=$(mktemp)
end=$(signin "{\"sub\":\"s\",\"email\":\"t-$STAMP@demo.test\",\"tokenFails\":true}" "$JAR")
case "$end" in *err=*) ok "a refused token exchange lands on a readable message" ;;
  *) bad "token failure handled" "ended on $end" ;; esac

# A token with no identity in it.
JAR=$(mktemp)
end=$(signin "{\"sub\":\"s\",\"email\":\"t2-$STAMP@demo.test\",\"noIdToken\":true}" "$JAR")
case "$end" in *err=*) ok "a response with no id_token lands on a readable message" ;;
  *) bad "missing id_token handled" "ended on $end" ;; esac

# The state cookie is single use: replaying the same callback must not work.
#
# Checked on the callback's OWN redirect rather than by following it. After the
# first use the jar holds a session, and /signup sends anyone already signed in
# on to their destination - so following the chain lands on /dashboard and
# looks like the replay succeeded when it did not. The refusal is the 302 the
# callback itself returns.
JAR=$(mktemp)
be "{\"sub\":\"sub-replay-$STAMP\",\"email\":\"replay-$STAMP@demo.test\",\"email_verified\":true}"
loc=$(curl -s -o /dev/null -c "$JAR" -w '%{redirect_url}' "$BASE/api/auth/google")
cb=$(curl -s -o /dev/null -b "$JAR" -c "$JAR" -w '%{redirect_url}' "$loc")
first=$(curl -s -o /dev/null -b "$JAR" -c "$JAR" -w '%{redirect_url}' "$cb")
case "$first" in
  */upload) ok "the first use of a callback signs the new person in" ;;
  *) bad "first use of callback" "went to $first" ;;
esac
grep -q jobstash_oauth "$JAR" \
  && bad "state cookie is consumed" "it is still in the jar after use" \
  || ok "the state cookie is consumed by its one use"
again=$(curl -s -o /dev/null -b "$JAR" -c "$JAR" -w '%{redirect_url}' "$cb")
case "$again" in
  *err=*) ok "the state cookie is single use - a replayed callback is refused" ;;
  *) bad "callback replay refused" "the replay redirected to $again" ;;
esac

echo
printf 'passed \033[32m%d\033[0m   failed \033[31m%d\033[0m\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
