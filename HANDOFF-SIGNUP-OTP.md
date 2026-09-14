# HANDOFF — Email code (OTP) on password sign-up

Written 2026-09-14. Branch `claude/signup-fetch-error` (cut from `master` at
`6abde26`). **Nothing committed, nothing pushed, not deployed.** The repo has
no git remote, so "push" isn't possible until one is added.

## What Justin asked for

1. Signing up with email and password showed Next's red "Failed to fetch"
   overlay on `localhost:3200/signup`.
2. Then he said signup shouldn't create the account straight away. It should
   **email a code to the address being registered, and the site should wait
   for that code**.
3. Mid-change he said "push to master right away". I pointed out there's no
   remote and asked what should go on master; **he dismissed the question**.
   The master decision is still open, see "Open decisions".

---

## Part 1 — "Failed to fetch" (done, checked in Chrome)

**Cause:** not the signup code. At 14:14 another Claude session ran
`opennextjs-cloudflare build` in `web/`, which deletes `.next` and killed the
dev server on port 3200 mid-request. See the memory note
`project_thejobstash_concurrent_web_builds`.

**Code bug it exposed:** `AuthCard.tsx` `submit()` didn't catch a rejected
`fetch`, so a dead server showed the overlay and left the button spinning.
It's now caught and shows "Couldn't reach the server. Check your connection
and try again." The button works again afterwards.

**Checked:** in real Chrome I faked a dead server (stubbed `fetch` to reject),
submitted, and read the page: the inline error was there, no overlay, button
enabled, and the server logged no `/api/auth` request. I couldn't save a
screenshot *file*, because the Chrome tool doesn't write to disk and the test
tab was a background tab in Justin's window.

That catch now lives in the shared `post()` helper described below.

---

## Part 2 — Email code on sign-up (written, NOT tested)

### How it works

```
Create account (email, password, consent)
  -> POST /api/auth/signup
       validate; rate-limit; refuse if the email already has an account
       hash password; make a 6-digit code; store hash(code) + password hash
       in signup_codes; email the code
     <- { ok: true, verify: true }            (no user row, no session yet)
Card switches to "Check your email" + code field
  -> POST /api/auth/signup/verify  { email, code }
       spend one try atomically; compare hash in constant time
       correct: createUser(email, stored hash), delete the code row,
       record signup-ip, create session
     <- { ok: true, redirect: "/upload" }
```

- Codes are **6 digits**, generated with rejection sampling so every value is
  equally likely. Only a **SHA-256 of `email:code`** is stored.
- A code lasts **10 minutes** and allows **5 tries**. The try is spent
  *before* comparing, in one `UPDATE … RETURNING`, so parallel guesses can't
  exceed the limit. When a code is expired or out of tries, its row is deleted
  and the user is told to send a new one.
- "Send a new code" calls `/api/auth/signup` again. The new code replaces the
  old one and resets the tries.
- Rate limits, all through the existing `trial_runs` table
  (`tooManyAttempts` / `recordAttempts`):
  - `signup-ip:<ip>`: 5 an hour. Checked when a code is sent, **recorded only
    when an account is actually created** (in verify). Same limit as before.
  - `code:<email>`: 5 codes an hour. Stops the form being used to flood
    someone's inbox.
  - `code-ip:<ip>`: 20 codes an hour.
- **Google sign-up is unchanged** and asks for no code, because Google has
  already verified the address. Login is unchanged. Existing accounts are not
  affected.
- If Google creates the same email while a code is pending, the `UNIQUE`
  email column makes verify fail, and it returns 409 "already an account".

### Email sending (`lib/mail.ts`)

- Sends through **Resend** (`POST https://api.resend.com/emails`), using the
  same env name `mailer.py` already reads: `JOBSTASH_RESEND_KEY`. The sender
  is `JOBSTASH_FROM`, defaulting to `TheJobStash <noreply@thejobstash.com>`.
- **No key and not a production build** (`next dev`): nothing is sent; the
  message, including the code, is printed to the dev-server console as
  `[mail] JOBSTASH_RESEND_KEY unset, not sent …`. This is how you test locally.
- **No key in a production build** (the live site, *and* `npm run preview`):
  throws. The signup route turns that into a 503 "We couldn't send the code
  just now… or sign up with Google", rather than claiming it sent one.

### Files changed

| File | Change |
|---|---|
| `web/migrations/0004_signup_codes.sql` | **New.** Table `signup_codes` (email PK, password_hash, code_hash, attempts, expires_at, created_at). **Applied to local D1 only.** |
| `db.py` | Same `signup_codes` table added to `SCHEMA` after `sessions`, since db.py is the single source of truth for the schema. |
| `web/lib/otp.ts` | **New.** `newCode`, `storeCode`, `checkCode`, `discardCode`, `MAX_TRIES`. |
| `web/lib/mail.ts` | **New.** `sendMail(to, subject, text, html)`. |
| `web/lib/cf.ts` | `Env` type gains `JOBSTASH_RESEND_KEY?` and `JOBSTASH_FROM?`. |
| `web/lib/db.ts` | `createUser(email, password)` became `createUser(email, hash)`: it no longer hashes. Only callers are the two signup routes (checked with tokensave). |
| `web/app/api/auth/signup/route.ts` | Rewritten: emails a code, returns `{ ok, verify: true }`, and no longer creates the user or session. |
| `web/app/api/auth/signup/verify/route.ts` | **New.** Checks the code, creates the user and session, redirects to `/upload`. |
| `web/app/signup/AuthCard.tsx` | New state `pending`, `code`, `note`. A shared `post()` helper (with the fetch catch), plus `go()`, `awaitCode()`, `verify()`, `resend()`, `changeEmail()`. The heading reads "Check your email" while pending. When `pending` is true, the code form replaces the normal form, the "or" divider, the Google button and the footer link. The code form has a numeric, `one-time-code`, 6-digit field, a Create account button, and "Send a new code · Use a different email". |

`db.ts`, `cf.ts`, `db.py` and the signup route **already had uncommitted
changes from the other session's credits remodel.** My edits are mixed in with
those, so they can't be committed as a separate change.

---

## The plan from here, in order

1. **Known gap, fix first:** `switchTo()` in `AuthCard.tsx` does `setMode(m);
   setErr("")` but not `setPending(false)`. Switching to Sign in while the code
   screen is up leaves it on screen. Add `setPending(false)` there.
2. **Type check:** `cd web && npx tsc --noEmit`. Nothing has been
   type-checked or built since these edits. Watch the JSX fragment wrapping the
   old form (`) : ( <> … </> )}`).
3. **Test in real Chrome** (workspace rule: user-facing changes must be tested
   in a real browser, with a screenshot):
   - Dev server: `preview_start` name `jobstash-web` (port 3200, `next dev`,
     which has the local D1 binding). **Before building or restarting, check no
     other session is building in `web/`**; see the concurrent-builds memory.
   - `/signup`: type a throwaway address, 8+ character password, tick consent
     with a *real click* (`form_input` on that checkbox was unreliable), then
     click Create account. Expect the "Check your email" screen.
   - Read the code from `preview_logs` (search `[mail]`).
   - Wrong code: "That code isn't right. 4 tries left." Right code: lands on
     `/upload`, signed in.
   - Also test: Send a new code (the old code must stop working), Use a
     different email, 6 wrong tries, an already-registered email (409), and
     the Sign in tab while pending (after fix 1).
   - Account creation: the previous agent would not create accounts itself.
     Justin may need to click the final step, or explicitly allow a throwaway
     local account.
   - Take a screenshot, send it, and delete test rows from local D1 afterwards.
4. **Commit / master.** Justin has to decide; see below.
5. **Before this goes live**, all Justin's:
   - Create a Resend account, verify `thejobstash.com` (SPF/DKIM), and add a
     **DMARC** record. `CLAUDE.md` already notes none exists.
   - `cd web && npx wrangler secret put JOBSTASH_RESEND_KEY`, and optionally
     `JOBSTASH_FROM`.
   - `npm run d1:migrate` so the live D1 gets `signup_codes`.
   - `npm run deploy`. Deploying the new signup route **without the key** makes
     password signup return 503 for everyone (Google still works).
6. Optional follow-ups, not started: a line in the Privacy Policy about the
   verification email; tidying `signup_codes` rows that expire and are never
   retried (they're small and overwritten on the next attempt, so low priority).

## Open decisions for Justin

- **"Push to master":** there's no git remote. Options offered: commit all 65
  uncommitted files, including the other session's credits work, to local
  `master`, either after testing or right away; or also create a private GitHub
  repo with `gh` and push. He dismissed the question, so nothing was done.
- Whether the live site should keep password signup open before Resend is
  configured (it will 503), or hold the deploy until the key is set.

## Environment notes

- A dev server started by this session may still be on port 3200
  (`preview_start` serverId `75e08a7c-…`). Stop it or reuse it.
- Another Claude session ("theJobstash credits model remodel") is active in
  this same working tree and was editing `web/app/dashboard/page.tsx` around
  14:32. Don't reset, stash or switch branches carelessly.
- Justin's own Chrome tab at `localhost:3200/signup` may still show the old
  overlay from before the fix; a reload clears it.
