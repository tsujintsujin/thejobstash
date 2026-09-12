import { NextRequest, NextResponse } from "next/server";
import { createUser, userByEmail, grantPlan } from "@/lib/db";
import { createSession } from "@/lib/session";

/** Mirrors /api/plan. "none" is not in here: it is the absence of a plan. */
const VALID_PLANS = ["one_time", "three_day", "seven_day"];
const NO_PLAN = "none";

export async function POST(req: NextRequest) {
  // Cast, not `any`: workerd types json() as `unknown` (Next typed it
  // `any`). Every field below is still String()-coerced and validated,
  // so this only names the shape - it does not trust it.
  const body = (await req.json().catch(() => ({}))) as Record<string, unknown>;
  const email = String(body.email || "").trim().toLowerCase();
  const password = String(body.password || "");
  const plan = String(body.plan || "seven_day");

  // Validated rather than trusted. grantPlan() falls back to a 1-day window on
  // an unrecognised id, so an unchecked value here quietly handed out a plan
  // nobody chose.
  if (plan !== NO_PLAN && !VALID_PLANS.includes(plan)) {
    return NextResponse.json({ error: "Unknown plan." }, { status: 400 });
  }

  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    return NextResponse.json({ error: "That email doesn't look right." }, { status: 400 });
  }
  if (password.length < 8) {
    return NextResponse.json(
      { error: "Use at least 8 characters." },
      { status: 400 }
    );
  }
  if (await userByEmail(email)) {
    return NextResponse.json(
      { error: "There's already an account with that email. Try signing in." },
      { status: 409 }
    );
  }

  const user = await createUser(email, password);
  // Payments are off, so the plan is granted immediately. With Stripe this
  // moves behind the webhook and nothing else changes.
  //
  // Signing up without one is allowed and leaves no entitlement row at all.
  // Everything downstream already copes: the dashboard reads "0 days" and
  // offers the picker, and delivery only ever serves entitled users.
  if (plan !== NO_PLAN) await grantPlan(user.id, plan);
  await createSession(user.id);

  return NextResponse.json({ ok: true, redirect: "/upload" });
}
