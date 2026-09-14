import { envVar } from "./cf";
import { db, newId, nowIso } from "./db";
import { chargePhp, type Pack } from "./packs";

/**
 * QR Ph through PayMongo's Payment Intent API, and the one function that turns
 * a payment into credits.
 *
 * The QR is shown in our own modal rather than on PayMongo's hosted checkout:
 * that page refuses to be framed, its layout cannot change, and its redirect
 * countdown is fixed. Here PayMongo hands back the QR image and we poll.
 *
 * Nothing trusts the browser or the webhook body. Both only ever say "go and
 * look at payment X"; settle() then asks PayMongo's API, with the secret key,
 * whether that intent succeeded and for how much.
 *
 * GCash and cards (once PayMongo approves them) are different flows - a GCash
 * redirect, a card form - so they will be their own branch, not a flag here.
 */
const API = "https://api.paymongo.com/v1";

export const PAYMENT_ID = /^pay_[0-9a-f]{16}$/;

async function pm(path: string, init: RequestInit = {}) {
  const key = envVar("PAYMONGO_SECRET_KEY");
  if (!key) throw new Error("Payments are not configured on this server.");
  const res = await fetch(API + path, {
    ...init,
    headers: {
      Authorization: "Basic " + btoa(key + ":"),
      "Content-Type": "application/json",
      Accept: "application/json",
    },
  });
  const j = (await res.json().catch(() => ({}))) as any;
  if (!res.ok) {
    const detail = j?.errors?.[0]?.detail || `HTTP ${res.status}`;
    console.error(`[paymongo] ${path}: ${detail}`);
    throw new Error(`PayMongo refused the request: ${detail}`);
  }
  return j.data;
}

const post = (path: string, attributes: Record<string, unknown>) =>
  pm(path, { method: "POST", body: JSON.stringify({ data: { attributes } }) });

/** Make a QR Ph code for one pack. The code expires after PayMongo's default 30 minutes. */
export async function createQr(userId: string, pack: Pack) {
  const id = newId("pay_");
  const amount = chargePhp(pack) * 100; // centavos

  // The row goes in before PayMongo is called, and the intent id is on it
  // before any QR exists - so a code that gets paid always has a row to credit.
  await db()
    .prepare(
      "INSERT INTO payments (id,user_id,pack,credits,amount,status,created_at) " +
        "VALUES (?,?,?,?,?,'pending',?)"
    )
    .bind(id, userId, pack.id, pack.credits, amount, nowIso())
    .run();

  const intent = await post("/payment_intents", {
    amount,
    currency: "PHP",
    payment_method_allowed: ["qrph"],
    description: `${pack.credits} TheJobStash credits`,
    metadata: { payment_id: id, user_id: userId, pack: pack.id },
  });
  await db()
    .prepare("UPDATE payments SET checkout_id=? WHERE id=?")
    .bind(intent.id, id)
    .run();

  const method = await post("/payment_methods", { type: "qrph" });
  const attached = await post(`/payment_intents/${intent.id}/attach`, {
    payment_method: method.id,
    client_key: intent.attributes.client_key,
  });

  // The image goes straight into an <img src> and a download link, so it must
  // be an image data URI and nothing else - never a URL or a javascript: link.
  const code = attached?.attributes?.next_action?.code;
  if (!/^data:image\/(png|jpeg);base64,[A-Za-z0-9+/=]+$/.test(code?.image_url || "")) {
    throw new Error("PayMongo did not return a QR code.");
  }
  return { id, qr: code.image_url as string, expiresAt: code.expires_at as string };
}

/** The payment row for a PayMongo intent id, for the webhook. */
export async function paymentForIntent(intentId: string) {
  const row = await db()
    .prepare("SELECT id FROM payments WHERE checkout_id=?")
    .bind(intentId)
    .first<{ id: string }>();
  return row?.id ?? null;
}

/**
 * Add a payment's credits if PayMongo says the intent succeeded in full. Safe
 * to call any number of times, from the modal's polling and the webhook at once.
 */
export async function settle(paymentId: string): Promise<"paid" | "pending" | "unknown"> {
  const p = await db()
    .prepare("SELECT id,user_id,credits,amount,checkout_id,status FROM payments WHERE id=?")
    .bind(paymentId)
    .first<any>();
  if (!p?.checkout_id) return "unknown";
  if (p.status === "paid") return "paid";

  const intent = await pm(`/payment_intents/${p.checkout_id}`);
  const paid =
    intent?.attributes?.status === "succeeded" && intent?.attributes?.amount === p.amount;
  if (!paid) return "pending";

  // One transaction. The credit UPDATE only fires while the row is still
  // pending, and the same transaction flips it - so the poll and the webhook
  // landing together add the credits once, not twice.
  await db().batch([
    db()
      .prepare(
        "UPDATE users SET credits=credits+? WHERE id=? AND EXISTS " +
          "(SELECT 1 FROM payments WHERE id=? AND status='pending')"
      )
      .bind(p.credits, p.user_id, p.id),
    db()
      .prepare("UPDATE payments SET status='paid', paid_at=? WHERE id=? AND status='pending'")
      .bind(nowIso(), p.id),
  ]);
  return "paid";
}
