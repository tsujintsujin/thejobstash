import { NextRequest, NextResponse } from "next/server";
import { recordAttempts, tooManyAttempts, userByEmail, verifyPassword } from "@/lib/db";
import { createSession, safeNext } from "@/lib/session";

export async function POST(req: NextRequest) {
  // Cast, not `any`: workerd types json() as `unknown` (Next typed it
  // `any`). Every field below is still String()-coerced and validated,
  // so this only names the shape - it does not trust it.
  const body = (await req.json().catch(() => ({}))) as Record<string, unknown>;
  const email = String(body.email || "").trim().toLowerCase();
  const password = String(body.password || "");

  // Checked before any password is hashed, so a flood of guesses costs a COUNT
  // each rather than 100,000 PBKDF2 rounds each.
  const ip = req.headers.get("cf-connecting-ip") || "unknown";
  const keys = [`login:${email}`, `login-ip:${ip}`];
  if ((await tooManyAttempts(keys[0], 10)) || (await tooManyAttempts(keys[1], 30))) {
    return NextResponse.json(
      { error: "Too many sign-in attempts. Wait 15 minutes and try again." },
      { status: 429 }
    );
  }

  const user = await userByEmail(email);
  // One message for both cases, so this endpoint can't be used to find out
  // which addresses have accounts.
  if (
    !user ||
    !user.password_hash ||
    !(await verifyPassword(password, user.password_hash))
  ) {
    await recordAttempts(...keys);
    return NextResponse.json(
      { error: "Wrong email or password." },
      { status: 401 }
    );
  }

  await createSession(user.id);
  // Re-validated here, not just on the login page: this is the value the
  // browser is actually told to follow, and it arrived in the request body.
  return NextResponse.json({ ok: true, redirect: safeNext(body.next) });
}
