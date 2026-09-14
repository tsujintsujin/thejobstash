import { NextRequest, NextResponse } from "next/server";
import { createUser, recordAttempts } from "@/lib/db";
import { checkCode, discardCode } from "@/lib/otp";
import { createSession } from "@/lib/session";

/** Second half of password sign-up: the emailed code creates the account. */
export async function POST(req: NextRequest) {
  const body = (await req.json().catch(() => ({}))) as Record<string, unknown>;
  const email = String(body.email || "").trim().toLowerCase();
  const code = String(body.code || "").replace(/\s/g, "");

  if (!/^\d{6}$/.test(code)) {
    return NextResponse.json({ error: "Enter the 6-digit code from the email." }, { status: 400 });
  }

  const check = await checkCode(email, code);
  if (!check.ok) {
    return NextResponse.json({ error: check.error }, { status: check.status });
  }

  // The address could have gained an account while the code sat in an inbox -
  // a Google sign-up, say. The UNIQUE email column is the check that cannot race.
  let user;
  try {
    user = await createUser(email, check.passwordHash);
  } catch {
    await discardCode(email);
    return NextResponse.json(
      { error: "There's already an account with that email. Try signing in." },
      { status: 409 }
    );
  }
  await discardCode(email);

  const ip = req.headers.get("cf-connecting-ip") || "unknown";
  await recordAttempts(`signup-ip:${ip}`);
  await createSession(user.id);

  return NextResponse.json({ ok: true, redirect: "/upload" });
}
