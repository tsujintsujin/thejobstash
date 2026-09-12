import { NextRequest, NextResponse } from "next/server";
import { currentUser } from "@/lib/session";
import { grantPlan } from "@/lib/db";

const VALID = ["one_time", "three_day", "seven_day"];

/**
 * Start a plan. Payments are switched off, so this grants the window directly.
 *
 * When Stripe is wired in, this route creates a Checkout session instead and
 * the webhook calls grantPlan() — the entitlement row it writes is identical,
 * so delivery, dashboard and the worker need no changes at all.
 */
export async function POST(req: NextRequest) {
  const user = await currentUser();
  if (!user) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  // Cast, not `any`: workerd types json() as `unknown` (Next typed it
  // `any`). Every field below is still String()-coerced and validated,
  // so this only names the shape - it does not trust it.
  const body = (await req.json().catch(() => ({}))) as Record<string, unknown>;
  const plan = String(body.plan || "");
  if (!VALID.includes(plan)) {
    return NextResponse.json({ error: "Unknown plan." }, { status: 400 });
  }

  await grantPlan(user.id, plan);
  return NextResponse.json({ ok: true, plan });
}
