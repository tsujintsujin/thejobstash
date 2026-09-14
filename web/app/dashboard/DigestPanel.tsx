"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ALERT, SPINNER } from "../ui";

/**
 * The one control on the dashboard: spend a credit to run this account's
 * resume and produce a digest.
 *
 * It renders NO job list. HANDOFF.md line 32 settled the scope of this page as
 * "Account only - resume, past digests", explicitly "Not a job browser". The
 * jobs live in the rendered digest, and the rendered digest has exactly one
 * way in: /api/download/<id>, the same route the Past digests rows use for
 * View and PDF. So a run ends in a modal that hands over that link rather than
 * re-implementing the list in React.
 *
 * A run can take minutes when the pool is stale and every board is swept
 * first, which outlasts any request Cloudflare will hold open. So /api/deliver
 * only starts the run, and this polls /api/runs/<id> until it lands.
 */
type Ready = { id: string; pdf: boolean; matches: number; near: number };

const POLL_MS = 4000;

export default function DigestPanel({
  hasProfile,
  credits,
}: {
  hasProfile: boolean;
  credits: number;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [ready, setReady] = useState<Ready | null>(null);

  // Escape closes, and the page behind must not scroll under the modal.
  useEffect(() => {
    if (!ready) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setReady(null);
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [ready]);

  async function run() {
    setErr("");
    setBusy(true);
    const r = await fetch("/api/deliver", { method: "POST" });
    const j = (await r.json().catch(() => ({}))) as any;
    if (!r.ok || !j.run_id) {
      setBusy(false);
      router.refresh();
      return setErr(j.error || "Something went wrong.");
    }
    // The credit is spent the moment the run starts, so the balance above
    // should say so while the run works.
    router.refresh();

    for (;;) {
      await new Promise((res) => setTimeout(res, POLL_MS));
      const s = await fetch(`/api/runs/${j.run_id}`, { cache: "no-store" });
      if (s.status === 401 || s.status === 404) {
        setBusy(false);
        return setErr("Lost track of that run. Refresh the page — it will appear under Past digests when it finishes.");
      }
      if (!s.ok) continue; // a blip, not an answer
      const st = (await s.json().catch(() => ({}))) as any;
      if (st.status === "done") {
        setBusy(false);
        setReady({
          id: st.delivery_id,
          pdf: !!st.pdf,
          matches: st.matches ?? 0,
          near: st.near_misses ?? 0,
        });
        // The delivery row is written, so the server render gains a Past
        // digests entry with the same two buttons the modal offers.
        return router.refresh();
      }
      if (st.status === "failed") {
        setBusy(false);
        router.refresh();
        return setErr(st.error || "The run failed. Your credit has been returned.");
      }
    }
  }

  if (!hasProfile) {
    return (
      <div className="border-3 border-ink bg-bone text-ink p-6 mb-8">
        <p className="text-sm font-semibold">
          Upload a resume and your digests will appear here.
        </p>
      </div>
    );
  }

  const empty = credits < 1;

  return (
    <>
      <div className="flex items-center gap-3 flex-wrap mb-5">
        <button className="btn btn-ink" onClick={run} disabled={busy || empty}>
          {busy && <span className={SPINNER} />}
          {busy ? "Sweeping and scoring…" : "Run my resume · 1 credit"}
        </button>
        <span className="text-sm font-semibold opacity-70">
          {busy ? (
            "This can take a couple of minutes. You can leave — it lands under Past digests."
          ) : empty ? (
            <>
              You&rsquo;re out of credits.{" "}
              <a href="#buy" className="underline">
                Buy a pack
              </a>
            </>
          ) : (
            "Opens your stash, and keeps a copy below"
          )}
        </span>
      </div>

      {err && <div className={ALERT}>{err}</div>}

      {ready && (
        <div
          className="fixed inset-0 z-[100] bg-ink/60 flex items-center
                     justify-center p-5 animate-fade"
          onClick={(e) => e.target === e.currentTarget && setReady(null)}
        >
          <div
            className="w-full max-w-[480px] bg-paper text-ink border-3 border-ink
                       shadow-brut-lg animate-pop"
            role="dialog"
            aria-modal="true"
            aria-label="Your stash is ready"
          >
            <div className="bg-ink text-bone px-4 py-3 flex justify-between items-center text-sm">
              <b>Your stash</b>
              <button
                className="bg-transparent border-0 text-bone text-[17px] cursor-pointer
                           leading-none px-1 py-0.5 font-[inherit]"
                onClick={() => setReady(null)}
                aria-label="Close"
              >
                ✕
              </button>
            </div>

            <div className="p-[22px] max-[560px]:p-[18px]">
              <h2 className="text-h3 mb-2">The Job Stash is ready!</h2>
              <p className="text-[13.5px] font-semibold opacity-75 mb-5">
                {ready.matches} match{ready.matches === 1 ? "" : "es"} and{" "}
                {ready.near} that came close, each with the reason it
                didn&rsquo;t clear. Nothing is held back.
              </p>

              <div className="flex gap-2.5 flex-wrap">
                {/* Byte-for-byte what the Past digests "View" button opens -
                    one route, one rendering, no second list to maintain. */}
                <a
                  className="btn btn-ink"
                  href={`/api/download/${ready.id}?format=html&v=${ready.id}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Click here to view →
                </a>
                {ready.pdf && (
                  <a
                    className="btn btn-paper"
                    href={`/api/download/${ready.id}?v=${ready.id}`}
                  >
                    PDF
                  </a>
                )}
              </div>

              <p className="text-xs opacity-70 mt-3.5 font-semibold">
                Also emailed to you, and kept under Past digests below.
              </p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
