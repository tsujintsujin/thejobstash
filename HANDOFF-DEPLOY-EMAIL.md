# HANDOFF-DEPLOY-EMAIL.md — hurdles, fixes, and what to do better

Covers the work of 2026-09-14 → 2026-09-15: moving deploys behind GitHub,
removing every PC → Cloudflare path, fixing Google sign-in, and making email
sign-up (OTP) work through Brevo. Read `CLAUDE.md` first; this is the story
behind the rules it now states.

**End state, verified in a real browser:**

- A push to `master` is the only way code reaches thejobstash.com
  (Cloudflare Workers Builds, root `web/`).
- The PC cannot deploy: wrangler is logged out, and `npm run deploy` refuses.
- Google sign-in works as a full-page redirect.
- Email sign-up sends a 6-digit code from `noreply@thejobstash.com` via Brevo,
  and the code arrives.

---

## 1. Deploys went straight from the PC's disk

**Hurdle.** `npm run deploy` ran wrangler, which uploads whatever is on disk.
Production could run code that existed in no commit, and it did.

**What we found on the way:**

| Problem | Evidence | Fix |
|---|---|---|
| `master` was 4 commits **behind** the live site | Live had credits and PayMongo; that code only existed on a feature branch, and some of it was uncommitted when it was deployed | Fast-forwarded `master` before connecting CI. Deploying `master` as-is would have removed payments from the live site. |
| A fresh GitHub clone **failed to build** | `Type error: Parameter 'd' implicitly has an 'any' type`. `cloudflare-env.d.ts` is gitignored, so a clean checkout has no D1 types. | `web/package.json` `prebuild` runs `wrangler types`. Proved by building a clean clone. |
| Google sign-in would silently break in CI | The client id and secret were inlined from `.env.local` at build time, and that file is not in git | Moved both to **Worker secrets**. Confirmed in Chrome that sign-in still worked. |
| Cloudflare's Build command field **didn't save** | After "Connect", the saved config showed Build command = `None` | Retyped it with real keystrokes, then reloaded to confirm it persisted |

**Result.** GitHub app "Cloudflare Workers and Pages" is installed on
`tsujintsujin` for this repo only. Preview builds are off. The first build
(`7f5723f`) and every merge since have built and gone live.

## 2. "Deploying from the PC refuses" was not enough

**Hurdle.** A refusing npm script is a sign on the door, not a lock. The PC's
wrangler was still logged in, and `preview`, `d1:migrate` and `d1:seed` all
still talked to Cloudflare.

**Fix:**

- `wrangler logout`, then checked `wrangler whoami` reported not authenticated.
- `.env.cloudflare`'s D1 token turned out to be empty. The scorer reaches D1
  through the Worker using its own app token, not a Cloudflare API credential.
- PR #2 removed `preview`, `d1:migrate` and `d1:seed`.
- Live D1 changes now go through the Cloudflare dashboard's D1 console.

## 3. The `.wrangler` folder

**Hurdle.** Local dev kept its database in `web/.wrangler/state`. The name
reads as deploy tooling, which is exactly what had just been removed.

**Fix.** Moved the database to `web/.localdb`, via `initOpenNextCloudflareForDev`'s
`persist` option and `d1:local --persist-to`, then deleted `.wrangler`. The only
thing that recreated it, `npm run preview` (it hardcodes `.wrangler/tmp`), was
removed.

## 4. Google sign-in popup never closed

**Hurdle.** Sign-in opened a popup. After Google, the popup stayed open, and
sometimes showed the dashboard inside it.

**Cause.** Google's pages set Cross-Origin-Opener-Policy, which severs
`window.opener`. After that, Chrome refuses the popup's `window.close()`.

**Fix (PR, commit `e97ff1d`).** Replaced it with a full-page redirect, the path
the link already used when popups were blocked. The Terms checkbox check was
kept. Verified from the home page modal:

1. Tick Terms.
2. Click Google: the same tab goes to Google's account chooser.
3. Pick the account: lands on `/dashboard`.

**Side trip.** "Sign in with Google → error" turned out to be the **local**
copy. Its callback is `http://localhost:3200` (set in `.dev.vars`), and the dev
server had stopped. It was not the live site.

## 5. The scorer died overnight

**Hurdle.** `py_server`, the tunnel and n8n all live in console windows. They
stopped, so live resume upload said "scorer is offline".

**Fix.** Restarted `scorer.cmd`. **Not fixed at the root.** It still dies with
its windows, and running it as a service needs elevation. This must be done
before the first paying customer.

## 6. Email sign-up (OTP)

**Hurdles, in order:**

1. **No email provider was configured.** `sendMail` threw "Email is not
   configured", and the card said "We couldn't send the code".
2. **The live D1 was missing `signup_codes`.** Migration `0004` had never been
   applied (`d1_migrations` showed 0001–0003). Applied through the D1 console
   and recorded as `0004_signup_codes.sql`.
3. **Resend → Brevo (PR #3).** `web/lib/mail.ts` now calls
   `POST https://api.brevo.com/v3/smtp/email` with `JOBSTASH_BREVO_KEY`.
4. **DNS.** The domain already had Titan email:
   - MX points to `mx1`/`mx2.titan.email`.
   - SPF is `v=spf1 include:spf.titan.email ~all`.

   Brevo's records were added **without touching Titan's**:

   | Type | Name | Value |
   |---|---|---|
   | TXT | `@` | `brevo-code:…` |
   | CNAME | `brevo1._domainkey` | `b1.thejobstash-com.dkim.brevo.com` (DNS only) |
   | CNAME | `brevo2._domainkey` | `b2.thejobstash-com.dkim.brevo.com` (DNS only) |
   | TXT | `_dmarc` | `v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com` |

   Brevo verified all four. The domain is **Authenticated**, and sender
   `TheJobStash <noreply@thejobstash.com>` is **Verified**.
5. **The key was saved as a plain Variable.** A plain variable is visible in the
   dashboard **and is wiped by the next GitHub deploy**. It was re-added as a
   **Secret**.
6. **The first Brevo key was unrecoverable.** Brevo shows a key once. A new key
   was generated.

## 7. Browser-automation hurdles (Claude in Chrome)

These cost the most time, and are worth knowing for next time:

- **Background tabs:** clicks and screenshots often silently fail.
- **Screenshots can close Cloudflare dialogs.**
- **Coordinate clicks miss if the page is still scrolling.** Read the
  element's position with JS first.
- **Cloudflare's "Add record" type picker would not switch A → CNAME under
  automation**, and the tab froze on Import. Justin added those three records
  by hand in about 2 minutes.
- **Scripted `form_input` sometimes doesn't reach React state.** The Build
  command field is the example: always reload and read back.
- **The tool's output filter blanks text that looks like keys or query
  strings.** Read values back as booleans or with spaced characters instead.

---

## What could have been done better

1. **Check what is live against `master` before wiring CI.** It was caught, but
   only after proposing to deploy `master`.
2. **Build from a clean clone before calling a pipeline ready.** The missing
   generated types would have failed the first CI build.
3. **"Refuses" should have meant "cannot".** Log wrangler out and remove every
   Cloudflare-touching script in the same step, rather than after being pushed.
4. **Don't point to a local URL without saying what works there.** Local Google
   sign-in cannot complete as configured, and that should have been said up
   front.
5. **Ask for the human step sooner.** About ten automation attempts at the
   Cloudflare DNS form were spent before asking Justin. Two minutes by hand
   beat twenty by script.
6. **Give exact dashboard instructions.** "Add variable" versus "+ Add", which
   of the two "Variables and secrets" sections, and **Type: Secret**. The vague
   version produced a plain variable that the next deploy would have erased.
7. **Say plainly when the permission system blocks an action.** Don't route
   around it. That is what happened with the D1 write, and it was right, but it
   needed Justin's explicit OK to proceed.
8. **Don't surface internal folder names** (`.wrangler`) or unrelated flags
   (Figma) in reports. They read as problems.

## Still open

- **Scorer as a service** (needs elevation). Blocks paying customers.
- **Digest issues seen during testing, not fixed:**
  - two near-misses wrongly blocked as "Anywhere in the World"
  - JobStreet descriptions leaking raw SVG
  - Hacker News titles are whole paragraphs
- **`mailer.py` (digest email) still references Resend.** Only sign-up codes use
  Brevo.
- **DMARC is `p=none` (monitoring only).** Tighten to `quarantine` once Brevo's
  reports look clean.
- **Justin's password login:** still needs `rehash_passwords.py`.
