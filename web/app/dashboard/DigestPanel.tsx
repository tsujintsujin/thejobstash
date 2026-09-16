"use client";

import { useEffect, useRef, useState } from "react";
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
  openRun,
}: {
  hasProfile: boolean;
  credits: number;
  /** A run still in progress, read server-side, so a refresh or a new
   *  sign-in renders the bar and a disabled button from the first paint. */
  openRun: { id: string; status: string; created_at: string } | null;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(!!openRun);
  const [err, setErr] = useState("");
  const [ready, setReady] = useState<Ready | null>(null);
  // Runs report a status, not a percentage, so the bar is stage plus elapsed
  // time: queued creeps to 15%, running eases toward 95% and only a finished
  // run fills it. It never goes backwards.
  const [pct, setPct] = useState(openRun ? 4 : 0);
  const [running, setRunning] = useState(openRun?.status === "running");
  // The current poll loop. Replacing it (or unmounting) stops the old one.
  const watching = useRef<object | null>(null);

  useEffect(() => {
    if (openRun) watch(openRun.id, Date.parse(openRun.created_at));
    return () => {
      watching.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openRun?.id]);

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
    setRunning(false);
    setPct(4);
    const t0 = Date.now();
    const r = await fetch("/api/deliver", { method: "POST" });
    const j = (await r.json().catch(() => ({}))) as any;
    if (!r.ok || !j.run_id) {
      setBusy(false);
      // A 409 means a run is already open (another tab, say); the refresh
      // brings its bar back.
      router.refresh();
      return setErr(j.error || "Something went wrong.");
    }
    // The credit is spent the moment the run starts, so the balance above
    // should say so while the run works.
    router.refresh();
    watch(j.run_id, t0);
  }

  async function watch(runId: string, t0: number) {
    const me = {};
    watching.current = me;
    setBusy(true);
    for (;;) {
      await new Promise((res) => setTimeout(res, POLL_MS));
      if (watching.current !== me) return;
      const s = await fetch(`/api/runs/${runId}`, { cache: "no-store" });
      if (s.status === 401 || s.status === 404) {
        setBusy(false);
        return setErr("Lost track of that run. Refresh the page — it will appear under Past digests when it finishes.");
      }
      if (!s.ok) continue; // a blip, not an answer
      const st = (await s.json().catch(() => ({}))) as any;
      const secs = (Date.now() - t0) / 1000;
      if (st.status === "queued") setPct((p) => Math.max(p, Math.min(15, 4 + secs / 2)));
      if (st.status === "running") {
        setRunning(true);
        setPct((p) => Math.max(p, 15 + 80 * (1 - Math.exp(-secs / 120))));
      }
      if (st.status === "done") {
        setPct(100);
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
          {busy ? "Scoring…" : "Run my resume · 1 credit"}
        </button>
        {busy ? (
          <div className="flex-1 min-w-[220px]">
            <div
              className="h-4 border-3 border-ink bg-paper overflow-hidden"
              role="progressbar"
              aria-label="Run progress"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(pct)}
            >
              {/* Eased over one poll interval, so it moves steadily between
                  answers instead of jumping every four seconds. */}
              <div
                className="h-full bg-jade transition-[width] duration-[4000ms] ease-linear"
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="block text-xs font-semibold opacity-70 mt-1.5">
              {running ? "Scoring your resume against the pool" : "Starting your run"} · You
              can leave — it lands under Past digests.
            </span>
          </div>
        ) : (
          empty && (
            <span className="text-sm font-semibold opacity-70">
              You&rsquo;re out of credits.{" "}
              <a href="#buy" className="underline">
                Buy a pack
              </a>
            </span>
          )
        )}
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
