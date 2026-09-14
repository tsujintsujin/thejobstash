import { NextRequest, NextResponse } from "next/server";
import { currentUser } from "@/lib/session";
import { db } from "@/lib/db";
import { PAYMENT_ID, settle } from "@/lib/paymongo";

/**
 * Has this payment gone through? The buy modal polls this while the QR is on
 * screen. Each call asks PayMongo and credits the account the moment the
 * intent succeeds, so the modal needs nothing from the webhook.
 */
export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const user = await currentUser();
  if (!user) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const { id } = await params;
  const own =
    PAYMENT_ID.test(id) &&
    (await db()
      .prepare("SELECT 1 FROM payments WHERE id=? AND user_id=?")
      .bind(id, user.id)
      .first());
  if (!own) return NextResponse.json({ error: "No such payment." }, { status: 404 });

  let status = "pending";
  try {
    status = await settle(id);
  } catch (e: any) {
    // A failed lookup is a "not yet", not an error to show: the next poll
    // asks again.
    console.error(`[pay] poll settle ${id}: ${e?.message || e}`);
  }
  return NextResponse.json({ status }, { headers: { "Cache-Control": "no-store" } });
}
