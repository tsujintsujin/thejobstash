import { cookies } from "next/headers";
import { db, nowIso, userById } from "./db";

/**
 * Server-side sessions in the sessions table, referenced by an httpOnly
 * cookie. Deliberately not a JWT: a row can be revoked, and there is already a
 * database sitting right there.
 *
 * Google sign-in is not wired up because it needs an OAuth client ID and
 * secret that only the account owner can create. The users table already
 * allows a NULL password_hash for exactly that case, so adding it later is a
 * route and a button, not a migration.
 */
const COOKIE = "jobstash_session";
const TTL_DAYS = 30;

export async function createSession(userId: string) {
  // Web Crypto, not node:crypto - this runs on a Worker now. Same 32 bytes.
  const token = [...crypto.getRandomValues(new Uint8Array(32))]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  const expires = new Date(Date.now() + TTL_DAYS * 86400000);
  await db()
    .prepare(
      "INSERT INTO sessions (token,user_id,created_at,expires_at) VALUES (?,?,?,?)"
    )
    .bind(token, userId, nowIso(), expires.toISOString())
    .run();

  (await cookies()).set(COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    expires,
    secure: process.env.NODE_ENV === "production",
  });
}

export async function destroySession() {
  const jar = await cookies();
  const token = jar.get(COOKIE)?.value;
  if (token) {
    await db().prepare("DELETE FROM sessions WHERE token=?").bind(token).run();
  }
  jar.delete(COOKIE);
}

export async function currentUser() {
  const token = (await cookies()).get(COOKIE)?.value;
  if (!token) return null;
  const row = await db()
    .prepare("SELECT user_id,expires_at FROM sessions WHERE token=?")
    .bind(token)
    .first<any>();
  if (!row) return null;
  if (new Date(row.expires_at) < new Date()) {
    await db().prepare("DELETE FROM sessions WHERE token=?").bind(token).run();
    return null;
  }
  return (await userById(row.user_id)) ?? null;
}

export async function requireUser() {
  const u = await currentUser();
  if (!u) throw new Error("UNAUTHENTICATED");
  return u;
}

/**
 * Where to send someone after they sign in.
 *
 * Only same-site absolute paths are allowed. Anything else - a full URL, a
 * protocol-relative `//evil.test`, a backslash Chrome normalises to a slash -
 * falls back to the dashboard. A login form that forwards to whatever the
 * query string says is an open redirect, and it is exactly the thing phishing
 * links use to borrow a real domain's credibility.
 */
export function safeNext(raw: unknown, fallback = "/dashboard") {
  const s = typeof raw === "string" ? raw.trim() : "";
  if (!s.startsWith("/")) return fallback;
  if (s.startsWith("//") || s.startsWith("/\\")) return fallback;
  if (s.startsWith("/api/")) return fallback;
  // `..` can only ever resolve to another same-origin path, so it is not an
  // escape - but it means the address bar and this value disagree, so drop it.
  if (s.split(/[/?#]/).includes("..")) return fallback;
  // Bouncing someone who just signed in back to a sign-in page is a loop that
  // terminates but still looks broken.
  const path = s.split(/[?#]/)[0].replace(/\/+$/, "");
  if (path === "/login" || path === "/signup") return fallback;
  return s;
}
