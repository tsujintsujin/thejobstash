import { NextRequest, NextResponse } from "next/server";
import { hashPassword, recordAttempts, tooManyAttempts, userByEmail } from "@/lib/db";
import { sendMail } from "@/lib/mail";
import { discardCode, newCode, storeCode } from "@/lib/otp";

/**
 * First half of password sign-up: email a code. No account exists until that
 * code comes back to /api/auth/signup/verify, so an address the person cannot
 * read never becomes an account. Sending again is calling this again - a new
 * code replaces the old one.
 */
export async function POST(req: NextRequest) {
  // Cast, not `any`: workerd types json() as `unknown` (Next typed it
  // `any`). Every field below is still String()-coerced and validated,
  // so this only names the shape - it does not trust it.
  const body = (await req.json().catch(() => ({}))) as Record<string, unknown>;
  const email = String(body.email || "").trim().toLowerCase();
  const password = String(body.password || "");

  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    return NextResponse.json({ error: "That email doesn't look right." }, { status: 400 });
  }
  if (password.length < 8) {
    return NextResponse.json(
      { error: "Use at least 8 characters." },
      { status: 400 }
    );
  }
  // Every account comes with a free run, so new accounts are the cheap way to
  // farm runs. Five an hour from one connection is past any household sharing it.
  // Recorded by the verify route, when an account actually gets created.
  const ip = req.headers.get("cf-connecting-ip") || "unknown";
  if (await tooManyAttempts(`signup-ip:${ip}`, 5, 60)) {
    return NextResponse.json(
      { error: "Too many new accounts from this connection. Try again later." },
      { status: 429 }
    );
  }
  // Each code is an email sent to whatever address was typed, which makes this
  // form a way to flood a stranger's inbox. Capped per address and per connection.
  if (
    (await tooManyAttempts(`code:${email}`, 5, 60)) ||
    (await tooManyAttempts(`code-ip:${ip}`, 20, 60))
  ) {
    return NextResponse.json(
      { error: "Too many codes requested. Wait an hour and try again." },
      { status: 429 }
    );
  }

  if (await userByEmail(email)) {
    return NextResponse.json(
      { error: "There's already an account with that email. Try signing in." },
      { status: 409 }
    );
  }

  const code = newCode();
  await storeCode(email, await hashPassword(password), code);
  await recordAttempts(`code:${email}`, `code-ip:${ip}`);

  try {
    await sendMail(
      email,
      `${code} is your TheJobStash code`,
      `Your TheJobStash sign-up code is ${code}.\n\n` +
        "It expires in 10 minutes. If you didn't try to create an account, " +
        "ignore this email - nothing happens without the code.",
      `<p>Your TheJobStash sign-up code is</p>` +
        `<p style="font-size:28px;font-weight:800;letter-spacing:6px">${code}</p>` +
        `<p>It expires in 10 minutes. If you didn't try to create an account, ` +
        `ignore this email - nothing happens without the code.</p>`
    );
  } catch {
    await discardCode(email);
    return NextResponse.json(
      { error: "We couldn't send the code just now. Try again in a minute, or sign up with Google." },
      { status: 503 }
    );
  }

  return NextResponse.json({ ok: true, verify: true });
}
