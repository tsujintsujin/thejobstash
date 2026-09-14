import { NextRequest, NextResponse } from "next/server";
import { paymentForIntent, settle } from "@/lib/paymongo";

/**
 * PayMongo's payment.paid webhook - what credits a payment when the buyer
 * closes the modal before it saw the payment land.
 *
 * ponytail: no Paymongo-Signature check. The body is only used to find which
 * payment to look up; settle() then asks PayMongo's API directly whether it
 * was paid, so a forged call can only trigger an honest lookup. Verify the
 * signature if this ever starts trusting the body itself.
 */
export async function POST(req: NextRequest) {
  const body = (await req.json().catch(() => null)) as any;
  const event = body?.data?.attributes;
  if (event?.type !== "payment.paid") return NextResponse.json({ ok: true });

  const intentId = event?.data?.attributes?.payment_intent_id;
  if (typeof intentId !== "string" || !/^pi_[A-Za-z0-9]+$/.test(intentId)) {
    return NextResponse.json({ ok: true });
  }

  try {
    const paymentId = await paymentForIntent(intentId);
    if (paymentId) await settle(paymentId);
  } catch (e: any) {
    console.error(`[pay] webhook settle ${intentId}: ${e?.message || e}`);
    // Non-2xx makes PayMongo retry, which is what a failed lookup wants.
    return NextResponse.json({ ok: false }, { status: 500 });
  }
  return NextResponse.json({ ok: true });
}
