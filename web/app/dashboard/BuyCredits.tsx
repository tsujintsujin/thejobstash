"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { ALERT, G3, SPINNER } from "../ui";
import { fetchJson } from "@/lib/fetcher";
import { PACKS, TEST_PRICE_PHP, chargePhp, packById } from "@/lib/packs";

/**
 * The credit packs, and the modal that takes the payment.
 *
 * Buy makes a QR Ph code (/api/pay) and shows it here rather than sending the
 * buyer off to PayMongo's page. The modal polls /api/pay/<id> until PayMongo
 * says paid, then counts down back to the dashboard, whose balance has
 * already been refreshed underneath it.
 */
type Pay = { id: string; qr: string; expiresAt: number; pack: string };

const POLL_MS = 3000;
const BACK_IN_S = 10;

function mmss(ms: number) {
  const s = Math.max(0, Math.ceil(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/**
 * Buying a pack, and the modal that shows its QR code. Shared by the
 * dashboard's packs and the home page's, so a signed-in buyer on the home page
 * pays right there. `afterPaid` runs when a paid modal closes.
 */
export function useBuy(afterPaid: () => void) {
  const router = useRouter();
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const [pay, setPay] = useState<Pay | null>(null);
  const [paidAt, setPaidAt] = useState(0);
  const [now, setNow] = useState(() => Date.now());

  async function buy(pack: string) {
    setErr("");
    setBusy(pack);
    const r = await fetch("/api/pay", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pack }),
    });
    const j = (await r.json().catch(() => ({}))) as any;
    setBusy("");
    if (!r.ok || !j.qr) return setErr(j.error || "Couldn't make a payment code.");
    setPaidAt(0);
    setNow(Date.now());
    setPay({ id: j.id, qr: j.qr, expiresAt: Date.parse(j.expiresAt), pack });
  }

  function close() {
    if (pay && !paidAt) {
      // One last look, in case it was paid in the seconds since the last poll.
      fetch(`/api/pay/${pay.id}`, { cache: "no-store" })
        .catch(() => null)
        .finally(() => router.refresh());
    }
    if (paidAt) afterPaid();
    setPay(null);
    setPaidAt(0);
  }

  // A clock for both countdowns, Escape to close, and no page scroll behind.
  useEffect(() => {
    if (!pay) return;
    const tick = setInterval(() => setNow(Date.now()), 250);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      clearInterval(tick);
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [pay, paidAt]);

  // Ask until PayMongo says paid. The balance refreshes at once, under the
  // modal. Coming back to the tab from a banking app asks straight away rather
  // than on the next tick; settle() credits once however often it is asked.
  useSWR(pay && !paidAt ? `/api/pay/${pay.id}` : null, fetchJson, {
    refreshInterval: POLL_MS,
    onSuccess: (j: any) => {
      if (j?.status === "paid" && !paidAt) {
        setPaidAt(Date.now());
        router.refresh();
      }
    },
  });

  const backIn = paidAt
    ? Math.max(0, BACK_IN_S - Math.floor((now - paidAt) / 1000))
    : BACK_IN_S;
  useEffect(() => {
    if (paidAt && backIn === 0) close();
  }, [paidAt, backIn]);

  const pack = pay ? packById(pay.pack) : undefined;
  const expired = !!pay && !paidAt && now >= pay.expiresAt;

  // Portalled to <body>: on the home page it opens from inside a pack card,
  // and the cards after it would otherwise paint over it.
  const modal =
    pay &&
    pack &&
    createPortal(
        <div
          className="fixed inset-0 z-[100] bg-ink/60 flex items-center
                     justify-center p-5 animate-fade"
          onClick={(e) => e.target === e.currentTarget && close()}
        >
          <div
            className="w-full max-w-[400px] max-h-full overflow-y-auto bg-paper
                       text-ink border-3 border-ink shadow-brut-lg animate-pop"
            role="dialog"
            aria-modal="true"
            aria-label="Pay with QR Ph"
          >
            <div className="bg-ink text-bone px-4 py-3 flex justify-between items-center text-sm">
              <b>
                {pack.credits} credits · ₱{chargePhp(pack)}
              </b>
              <button
                className="bg-transparent border-0 text-bone text-[17px] cursor-pointer
                           leading-none px-1 py-0.5 font-[inherit]"
                onClick={close}
                aria-label="Close"
              >
                ✕
              </button>
            </div>

            <div className="p-[22px] max-[560px]:p-[18px] text-center">
              {paidAt ? (
                <>
                  <h2 className="text-h3 mb-2">Payment received!</h2>
                  <p className="text-[13.5px] font-semibold opacity-75 mb-5">
                    {pack.credits} credits added to your balance.
                  </p>
                  <div
                    className="text-[64px] font-extrabold leading-none tracking-[-0.03em]"
                    aria-live="polite"
                  >
                    {backIn}
                  </div>
                  <p className="text-[11px] font-extrabold uppercase tracking-[0.09em] opacity-70 mt-2 mb-5">
                    Back to your dashboard in {backIn} second{backIn === 1 ? "" : "s"}
                  </p>
                  <button className="btn btn-ink" onClick={close}>
                    Back now
                  </button>
                </>
              ) : expired ? (
                <>
                  <h2 className="text-h3 mb-2">This code expired</h2>
                  <p className="text-[13.5px] font-semibold opacity-75 mb-5">
                    Nothing was charged. Close this and press Buy again for a
                    fresh code.
                  </p>
                  <button className="btn btn-ink" onClick={close}>
                    Close
                  </button>
                </>
              ) : (
                <>
                  <h2 className="text-h3 mb-1">Scan to pay</h2>
                  <p className="text-[13px] font-semibold opacity-75 mb-4">
                    Open GCash, Maya or your bank app and scan this QR Ph code.
                  </p>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={pay.qr}
                    alt="QR Ph code for this payment"
                    width={232}
                    height={232}
                    className="mx-auto w-[232px] h-[232px] border-3 border-ink bg-white p-2"
                  />
                  <div className="flex items-center justify-center gap-2 mt-4 text-[13px] font-bold">
                    <span className="inline-block w-2.5 h-2.5 bg-jade border-2 border-ink animate-pulse" />
                    Waiting for payment · expires in {mmss(pay.expiresAt - now)}
                  </div>
                  <a
                    href={pay.qr}
                    download="thejobstash-qr.png"
                    className="btn btn-paper btn-sm mt-4"
                  >
                    Save QR image
                  </a>
                  <p className="text-xs font-semibold opacity-65 mt-3 leading-[1.45]">
                    On your phone? Save the image, then upload it from your
                    wallet&rsquo;s scan screen.
                  </p>
                </>
              )}
            </div>
          </div>
        </div>
  ,
      document.body
    );

  return { buy, busy, err, open: !!pay, modal };
}

/* Only the recommended pack wears an accent — three coloured cards would rank
   nothing. Jade because it is a recommendation, not a warning. */
export default function BuyCredits() {
  const router = useRouter();
  const { buy, busy, err, open, modal } = useBuy(() => {
    router.refresh();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  return (
    <>
      {err && <div className={ALERT}>{err}</div>}
      <div className={`${G3} mb-2.5`}>
        {PACKS.map((p, i) => (
          <div key={p.id} className={`card ${i === 1 ? "bg-jade" : "bg-paper"}`}>
            <b className="text-[17px]">{p.credits} credits</b>
            <p className="text-[13px] font-semibold opacity-70 mt-1 mb-3.5">
              ₱{chargePhp(p)}
              {TEST_PRICE_PHP !== null && <s className="ml-1.5">₱{p.php}</s>} ·{" "}
              {p.credits} runs
            </p>
            <button
              className="btn btn-ink btn-sm"
              onClick={() => buy(p.id)}
              disabled={!!busy || open}
            >
              {busy === p.id && <span className={SPINNER} />}
              {busy === p.id ? "Making your code…" : "Buy"}
            </button>
          </div>
        ))}
      </div>


      {modal}
    </>
  );
}
