import { env } from "./cf";

/**
 * The web app and the Python worker share one Cloudflare D1 database.
 *
 * D1 is SQLite, so every query here is the same SQL it was when this ran
 * against a local file - `datetime('now','-3 days')` and `ON CONFLICT DO
 * UPDATE` included. What changed is that D1 is reached over the network, so
 * the whole surface is async. Callers await; nothing else moved.
 *
 * Schema lives in web/migrations/ and is applied by wrangler. Python reads and
 * writes the same database through d1.py, so there is still one source of
 * truth for the shape and one pool of jobs.
 */
export function db(): D1Database {
  return env().DB;
}

export const nowIso = () => new Date().toISOString().replace(/\.\d+Z$/, "Z");
export const todayIso = () => new Date().toISOString().slice(0, 10);

export const newId = (prefix = "") =>
  prefix +
  [...crypto.getRandomValues(new Uint8Array(8))]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");

/**
 * Mirrors db.py's pbkdf2 format exactly, so either side can verify a login.
 *
 * Web Crypto rather than node:crypto: this runs on a Worker now, and
 * `pbkdf2Sync` would block the single thread for the whole derivation.
 *
 * 100,000 is workerd's hard ceiling - it throws NotSupportedError above it -
 * so this is the platform's number, not a knob turned down to fit a budget.
 * db.py's PBKDF2_ROUNDS must stay identical: a password set on one side is
 * verified on the other, and a mismatch locks everybody out silently.
 */
const ROUNDS = 100000;

async function pbkdf2(password: string, salt: string, rounds: number) {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveBits"]
  );
  const bits = await crypto.subtle.deriveBits(
    {
      name: "PBKDF2",
      hash: "SHA-256",
      salt: new TextEncoder().encode(salt),
      iterations: rounds,
    },
    key,
    256
  );
  return [...new Uint8Array(bits)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export async function hashPassword(password: string, salt?: string) {
  const s =
    salt ||
    [...crypto.getRandomValues(new Uint8Array(16))]
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  return `pbkdf2$${ROUNDS}$${s}$${await pbkdf2(password, s, ROUNDS)}`;
}

export async function verifyPassword(password: string, stored: string) {
  try {
    const [, rounds, salt, want] = (stored || "").split("$");
    if (!rounds || !salt || !want) return false;
    const n = parseInt(rounds, 10);
    // A hash written before the move used 120,000, which workerd refuses
    // outright. Caught below either way, but saying so makes the difference
    // between "wrong password" and "this account predates the migration"
    // visible in the logs instead of guessable.
    if (n > ROUNDS) {
      console.error(`[auth] stored hash uses ${n} rounds; workerd caps at ${ROUNDS}`);
      return false;
    }
    const got = await pbkdf2(password, salt, n);
    // Constant-time: comparing hex with === leaks how much of it matched.
    if (got.length !== want.length) return false;
    let diff = 0;
    for (let i = 0; i < got.length; i++) diff |= got.charCodeAt(i) ^ want.charCodeAt(i);
    return diff === 0;
  } catch {
    return false;
  }
}

export type User = {
  id: string;
  email: string;
  password_hash: string | null;
  google_sub?: string | null;
};

const USER_COLS = "id,email,password_hash,google_sub";

export async function userByEmail(email: string) {
  return db()
    .prepare(`SELECT ${USER_COLS} FROM users WHERE email = ?`)
    .bind(email.trim().toLowerCase())
    .first<User>();
}

export async function userById(id: string) {
  return db().prepare(`SELECT ${USER_COLS} FROM users WHERE id = ?`).bind(id).first<User>();
}

export async function createUser(email: string, password: string): Promise<User> {
  const id = newId("usr_");
  const e = email.trim().toLowerCase();
  const hash = await hashPassword(password);
  await db()
    .prepare("INSERT INTO users (id,email,password_hash,created_at) VALUES (?,?,?,?)")
    .bind(id, e, hash, nowIso())
    .run();
  // Returns the hash it actually stored. This used to hand back `null`, which
  // is what an OAuth-only account looks like - so any caller that checked
  // "does this account have a password" would have been told no about an
  // account that had just been given one.
  return { id, email: e, password_hash: hash, google_sub: null };
}

export async function userByGoogleSub(sub: string) {
  return db()
    .prepare(`SELECT ${USER_COLS} FROM users WHERE google_sub = ?`)
    .bind(sub)
    .first<User>();
}

/**
 * An account created by Google, with no password. `password_hash` stays NULL,
 * and /api/auth/login already refuses a NULL hash - so an OAuth-only address
 * cannot be signed into by guessing an empty password.
 */
export async function createOAuthUser(email: string, googleSub: string): Promise<User> {
  const id = newId("usr_");
  const e = email.trim().toLowerCase();
  await db()
    .prepare(
      "INSERT INTO users (id,email,password_hash,google_sub,created_at) " +
        "VALUES (?,?,NULL,?,?)"
    )
    .bind(id, e, googleSub, nowIso())
    .run();
  return { id, email: e, password_hash: null, google_sub: googleSub };
}

/**
 * Attach Google to an account that already exists under the same address.
 * Only ever called with an email Google reported as verified: without that
 * check, anyone able to set an unverified Google address to someone else's
 * email could claim their account.
 */
export async function linkGoogleSub(userId: string, googleSub: string) {
  await db()
    .prepare("UPDATE users SET google_sub=? WHERE id=?")
    .bind(googleSub, userId)
    .run();
}

/**
 * Payment is switched off, so a plan is granted on request. When Stripe lands
 * it writes exactly this row after the webhook clears - nothing downstream
 * needs to change.
 */
const PLAN_DAYS: Record<string, number> = {
  one_time: 1,
  three_day: 3,
  seven_day: 7,
};

export async function grantPlan(userId: string, plan: string) {
  const days = PLAN_DAYS[plan] ?? 1;
  const start = new Date();
  const end = new Date(start.getTime() + (days - 1) * 86400000);
  // Batched so the supersede and the insert land together. Without it a
  // dropped connection between the two leaves an account with no active
  // entitlement at all - having just been granted one.
  await db().batch([
    db()
      .prepare("UPDATE entitlements SET status='superseded' WHERE user_id=?")
      .bind(userId),
    db()
      .prepare(
        "INSERT INTO entitlements (id,user_id,plan,starts_on,ends_on," +
          "deliveries_used,status,created_at) VALUES (?,?,?,?,?,0,'active',?)"
      )
      .bind(
        newId("ent_"),
        userId,
        plan,
        start.toISOString().slice(0, 10),
        end.toISOString().slice(0, 10),
        nowIso()
      ),
  ]);
}

export async function activeEntitlement(userId: string) {
  const day = todayIso();
  return db()
    .prepare(
      "SELECT * FROM entitlements WHERE user_id=? AND status='active' " +
        "AND starts_on<=? AND ends_on>=? ORDER BY created_at DESC LIMIT 1"
    )
    .bind(userId, day, day)
    .first<any>();
}

export async function deliveriesFor(userId: string) {
  const { results } = await db()
    .prepare(
      "SELECT id,day,matches,near_misses,html_path,pdf_path,email_status," +
        "created_at FROM deliveries WHERE user_id=? ORDER BY created_at DESC LIMIT 30"
    )
    .bind(userId)
    .all<any>();
  return results ?? [];
}

export async function profileFor(userId: string) {
  return db()
    .prepare("SELECT resume_name,profile_json,updated_at FROM profiles WHERE user_id=?")
    .bind(userId)
    .first<any>();
}

export async function saveProfile(
  userId: string,
  resumeName: string,
  resumeText: string,
  profileJson: string
) {
  await db()
    .prepare(
      "INSERT INTO profiles (user_id,resume_name,resume_text,profile_json,updated_at) " +
        "VALUES (?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET " +
        "resume_name=excluded.resume_name, resume_text=excluded.resume_text, " +
        "profile_json=excluded.profile_json, updated_at=excluded.updated_at"
    )
    .bind(userId, resumeName, resumeText.slice(0, 20000), profileJson, nowIso())
    .run();
}

export async function poolStats() {
  // One round trip instead of three. Each D1 query is a network call, and
  // this runs on the home page.
  const row = await db()
    .prepare(
      "SELECT COUNT(*) pool, " +
        "SUM(CASE WHEN first_seen >= datetime('now','-3 days') THEN 1 ELSE 0 END) fresh, " +
        "COUNT(DISTINCT source) sources FROM jobs"
    )
    .first<any>();
  return {
    pool: row?.pool ?? 0,
    fresh: row?.fresh ?? 0,
    sources: row?.sources ?? 0,
  };
}
