import { NextRequest, NextResponse } from "next/server";
import { currentUser } from "@/lib/session";
import { packById } from "@/lib/packs";
import { createQr } from "@/lib/paymongo";
import { db } from "@/lib/db";

/**
 * Make a QR Ph code for one credit pack, for the buy modal to show.
 *
 * Credits are NOT added here. Only settle() adds them, once PayMongo itself
 * says the money arrived - reached from the modal's polling or the webhook.
 */
export async function POST(req: NextRequest) {
  const user = await currentUser();
  if (!user) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const body = (await req.json().catch(() => ({}))) as Record<string, unknown>;
  const pack = packById(String(body.pack || ""));
  if (!pack) return NextResponse.json({ error: "Unknown pack." }, { status: 400 });

  // Every code is a round trip to PayMongo on this account. Five unpaid ones
  // in ten minutes is well past anyone actually buying.
  const unpaid = await db()
    .prepare(
      "SELECT COUNT(*) n FROM payments WHERE user_id=? AND status='pending' " +
        "AND created_at > strftime('%Y-%m-%dT%H:%M:%SZ','now','-10 minutes')"
    )
    .bind(user.id)
    .first<{ n: number }>();
  if ((unpaid?.n ?? 0) >= 5) {
    return NextResponse.json(
      { error: "Too many unpaid codes in a row. Use the one you have, or try again in a few minutes." },
      { status: 429 }
    );
  }

  try {
    return NextResponse.json(await createQr(user.id, pack));
  } catch (e: any) {
    return NextResponse.json(
      { error: e?.message || "Couldn't make a payment code." },
      { status: 502 }
    );
  }
}
