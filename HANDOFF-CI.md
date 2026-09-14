# HANDOFF-CI.md — put TheJobStash's deploys behind git

**Status: not built. This is the task.**
Written 2026-09-14. Read `CLAUDE.md` first, then this.

---

## The problem you are fixing

`npm run deploy` uploads **whatever files are sitting on this disk** to
Cloudflare. wrangler never reads git. Consequences today:

- Production can run code that exists in no commit, on no branch, nowhere but
  one hard drive.
- The deployed Worker version cannot be mapped back to a commit.
- Nothing gates it. No branch protection, no review, no CI.

Until 2026-09-14 the project had no GitHub remote at all — `git init` was run
2026-09-12, two days into the build, and stopped there. It is on GitHub now:
**https://github.com/tsujintsujin/thejobstash** (private, default branch
`master`).

A stopgap landed the same day: `web/scripts/predeploy.js`, wired as npm's
`predeploy` hook, refuses a manual deploy unless HEAD is clean and pushed.
**That is a seatbelt, not the fix.** Justin's other 8 projects deploy through
Vercel on `git push`. This one should behave the same way.

## The goal

Push to `master` → CI builds → Cloudflare Worker updates. Manual
`npm run deploy` from a laptop stops being the path to production.

---

## What you are wiring up

| | |
|---|---|
| Repo | `tsujintsujin/thejobstash` (private) |
| Worker | `thejobstash` |
| Domains | `thejobstash.com`, `www.thejobstash.com` (custom domains, already set) |
| D1 | `jobstash` · `62bf7121-3b14-4af2-bf67-6ae4dabf1a36` |
| Build | `npx opennextjs-cloudflare build` |
| Deploy | `npx opennextjs-cloudflare deploy` |
| Config | `web/wrangler.jsonc` |
| App root | `web/` — **not the repo root** |

Two options. **Recommended: GitHub Actions.** Cloudflare Workers Builds is the
other, but OpenNext needs a specific Node version and build step, and Actions
gives control over both plus a place to run the Python tests. Decide, do not
do both.

---

## Traps — read before writing the workflow

1. **Google credentials are inlined at build time, not read at runtime.**
   `web/.env.local` holds `JOBSTASH_GOOGLE_CLIENT_ID` and
   `JOBSTASH_GOOGLE_CLIENT_SECRET`. Next bakes them into the bundle during
   `next build`. That file is **gitignored and will not exist in CI**, so a CI
   build without them produces a Worker where **every Google sign-in fails**
   with `redirect_uri_mismatch` or a missing client id — and it will deploy
   perfectly happily. Put both in GitHub Actions secrets and write `.env.local`
   in a step before the build. Get the live values from Justin's
   `web/.env.local`; do not invent them.

2. **Worker secrets are NOT build-time and must not be touched.**
   `JOBSTASH_PY_TOKEN` and `PAYMONGO_SECRET_KEY` already live on the Worker
   (`wrangler secret list`). CI needs a `CLOUDFLARE_API_TOKEN` to deploy, and
   must **not** re-put those two — re-putting with a wrong value breaks live
   payments.

3. **`predeploy.js` will fail in CI.** It runs on `npm run deploy` and checks
   `git status --porcelain` plus `origin/<branch>`. In CI, call the two
   OpenNext commands directly, or set `ALLOW_DIRTY_DEPLOY=1`. Do not delete
   the script — it still guards manual deploys from Justin's machine.

4. **D1 migrations do not run themselves.** `npm run d1:migrate` applies
   `web/migrations/` to the remote DB. Decide deliberately whether CI runs it.
   Safer: leave it manual. A migration is a one-way door — rolling back a
   Worker version does not undo a dropped column.

5. **Half the product is not on Cloudflare.** The Python scorer runs on
   Justin's PC behind a tunnel (`scorer.thejobstash.com`). CI deploys the site
   only. Nothing about this task touches `py_server.py`, `matching.py` or the
   local job pool, and CI must not try to run `test_matching.py` against a
   pool it does not have.

6. **Cloudflare account id** is not in `wrangler.jsonc` and not in
   `.env.cloudflare`. Ask Justin, or read it from `wrangler whoami`.

---

## Rollback must keep working

Cloudflare stores every deployed version. This is the real safety net and CI
must not obscure it:

```bash
cd web && npx wrangler versions list      # find the good one
cd web && npx wrangler rollback <version-id>
```

Rollback restores **code only** — never the database.

After CI exists, make the version traceable to a commit: pass the short SHA as
the deploy message so `wrangler deployments list` shows which commit is live.

---

## Definition of done

- [ ] Push to `master` deploys, verified by a real trivial commit
- [ ] `thejobstash.com` loads afterwards — **opened in a real browser, not curl**
- [ ] **Google sign-in still works after a CI-built deploy** — this is the one
      that will silently break (trap 1). Click through it.
- [ ] Buy-credits modal still renders a QR (payments secret untouched)
- [ ] `npx wrangler rollback` still works
- [ ] Manual `npm run deploy` from Justin's machine still works, guard intact
- [ ] `CLAUDE.md` updated — its "no CI, deploys go straight from this disk"
      line becomes wrong the moment this ships

## Context Justin wants respected

- Branch first, never edit `master` directly.
- Do not commit without being asked.
- Never commit `.env.cloudflare`, `jobstash.db`, `web/seed.sql`, `outbox/`.
- A user-facing change is not verified until it has been clicked in a real
  browser and screenshotted. An HTTP 200 is not verification.
