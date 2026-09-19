"use client";

import { useRouter } from "next/navigation";
import { SPINNER } from "./ui";
import { useBuy } from "./dashboard/BuyCredits";

/** A home-page pack's Buy, for a signed-in visitor: pays here, then the dashboard. */
export default function BuyButton({ pack }: { pack: string }) {
  const router = useRouter();
  const { buy, busy, err, open, modal } = useBuy(() => router.push("/dashboard"));
  return (
    <>
      <button
        className="btn btn-ink mt-auto text-center"
        onClick={() => buy(pack)}
        disabled={!!busy || open}
      >
        {busy && <span className={SPINNER} />}
        {busy ? "Making your code…" : "Buy credits"}
      </button>
      {err && <p className="text-[13px] font-bold mt-2">{err}</p>}
      {modal}
    </>
  );
}
