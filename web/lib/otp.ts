import { db, nowIso } from "./db";

/**
 * The emailed code that password sign-up has to type back before an account
 * is created. Rows live in signup_codes (migration 0004).
 */
const TTL_MINUTES = 10;
export const MAX_TRIES = 5;

async function sha256(s: string) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Six digits. Rejection sampling keeps every code equally likely. */
export function newCode() {
  const buf = new Uint32Array(1);
  do crypto.getRandomValues(buf);
  while (buf[0] >= 4_294_000_000); // the largest multiple of 1e6 below 2^32
  return String(buf[0] % 1_000_000).padStart(6, "0");
}

/** A new code replaces any earlier one for the address, and resets its tries. */
export async function storeCode(email: string, passwordHash: string, code: string) {
  const expires = new Date(Date.now() + TTL_MINUTES * 60000)
    .toISOString()
    .replace(/\.\d+Z$/, "Z");
  await db()
    .prepare(
      "INSERT INTO signup_codes (email,password_hash,code_hash,attempts,expires_at,created_at) " +
        "VALUES (?,?,?,0,?,?) ON CONFLICT(email) DO UPDATE SET " +
        "password_hash=excluded.password_hash, code_hash=excluded.code_hash, " +
        "attempts=0, expires_at=excluded.expires_at, created_at=excluded.created_at"
    )
    .bind(email, passwordHash, await sha256(`${email}:${code}`), expires, nowIso())
    .run();
}

export async function discardCode(email: string) {
  await db().prepare("DELETE FROM signup_codes WHERE email=?").bind(email).run();
}

export type CodeCheck =
  | { ok: true; passwordHash: string }
  | { ok: false; status: number; error: string };

export async function checkCode(email: string, code: string): Promise<CodeCheck> {
  // The try is spent before the comparison, in one statement, so parallel
  // guesses cannot all read the same count and get past MAX_TRIES together.
  const row = await db()
    .prepare(
      "UPDATE signup_codes SET attempts=attempts+1 " +
        "WHERE email=? AND attempts<? AND expires_at>? " +
        "RETURNING password_hash,code_hash,attempts"
    )
    .bind(email, MAX_TRIES, nowIso())
    .first<{ password_hash: string; code_hash: string; attempts: number }>();

  if (!row) {
    await discardCode(email);
    return {
      ok: false,
      status: 410,
      error: "That code has expired or run out of tries. Send a new one.",
    };
  }

  const got = await sha256(`${email}:${code}`);
  let diff = got.length ^ row.code_hash.length;
  for (let i = 0; i < got.length; i++) diff |= got.charCodeAt(i) ^ row.code_hash.charCodeAt(i);
  if (diff !== 0) {
    const left = MAX_TRIES - row.attempts;
    return {
      ok: false,
      status: 400,
      error: left
        ? `That code isn't right. ${left} ${left === 1 ? "try" : "tries"} left.`
        : "That code isn't right, and that was the last try. Send a new one.",
    };
  }
  return { ok: true, passwordHash: row.password_hash };
}
