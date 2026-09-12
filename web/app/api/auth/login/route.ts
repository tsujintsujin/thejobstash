import { NextRequest, NextResponse } from "next/server";
import { userByEmail, verifyPassword } from "@/lib/db";
import { createSession, safeNext } from "@/lib/session";

export async function POST(req: NextRequest) {
  // Cast, not `any`: workerd types json() as `unknown` (Next typed it
  // `any`). Every field below is still String()-coerced and validated,
  // so this only names the shape - it does not trust it.
  const body = (await req.json().catch(() => ({}))) as Record<string, unknown>;
  const email = String(body.email || "").trim().toLowerCase();
  const password = String(body.password || "");

  const user = await userByEmail(email);
  // One message for both cases, so this endpoint can't be used to find out
  // which addresses have accounts.
  if (
    !user ||
    !user.password_hash ||
    !(await verifyPassword(password, user.password_hash))
  ) {
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
