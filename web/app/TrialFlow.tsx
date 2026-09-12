"use client";

import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import JobCard from "./JobCard";

/**
 * The free trial: upload -> Start -> See Results, with no account.
 *
 * The locked cards render bar widths the API invented. There is no job data
 * behind the blur to recover, because the server never sent any - the blur is
 * presentation, the paywall is the payload.
 */
import type { Job } from "./JobCard";
type Visible = Job;

type Trial = {
  visible?: Visible;
  locked?: { bars: number[] }[];
  locked_total?: number;
  empty?: boolean;
  summary: {
    matches: number;
    near_misses: number;
    pool: number;
    scored: number;
    skills: number;
    years: number;
    level: string;
    families: string[];
    top_skills: string[];
  };
};

type Stage = "idle" | "ready" | "running" | "done";

const SPINNER =
  "inline-block w-[15px] h-[15px] border-3 border-ink border-t-transparent " +
  "rounded-full animate-spin align-[-2px] mr-2";
/* Hard errors invert rather than turning red. Red here would be flare, which
   on every other surface means "this is the button" - an error styled as the
   primary action is exactly the collision this palette exists to remove. */
const ALERT =
  "border-3 border-ink bg-ink text-bone px-[15px] py-[13px] text-sm font-bold mb-[18px]";
const STAT = "border-3 border-ink shadow-brut text-ink px-5 py-[18px]";
const STAT_N =
  "block text-[38px] font-extrabold tracking-[-0.03em] leading-none";
const STAT_L =
  "text-[11px] font-extrabold uppercase tracking-[0.09em] opacity-70";
const G4 =
  "grid gap-4 grid-cols-4 max-[900px]:grid-cols-2 max-[620px]:grid-cols-1";

export default function TrialFlow({ label }: { label: string }) {
  const [open, setOpen] = useState(false);
  const [stage, setStage] = useState<Stage>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [err, setErr] = useState("");
  const [over, setOver] = useState(false);
  const [trial, setTrial] = useState<Trial | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [mount, setMount] = useState<HTMLElement | null>(null);

  // The portal target only exists after hydration.
  useEffect(() => setMount(document.getElementById("trial-results")), []);

  // Escape closes, and the background must not scroll behind the modal.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && stage !== "running") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, stage]);

  function pick(f: File) {
    setErr("");
    setFile(f);
    setStage("ready");
  }

  async function start() {
    if (!file) return;
    setErr("");
    setStage("running");
    const fd = new FormData();
    fd.append("resume", file);
    const r = await fetch("/api/trial", { method: "POST", body: fd });
    const j = (await r.json()) as any;
    if (!r.ok) {
      setErr(j.error || "Something went wrong.");
      setStage("ready");
      return;
    }
    setTrial(j);
    setStage("done");
  }

  function reveal() {
    setOpen(false);
    // Let the modal unmount before scrolling, or the scroll lands mid-teardown.
    setTimeout(() => {
      document
        .getElementById("trial-results")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 80);
  }

  return (
    <>
      <button
        className="btn"
        onClick={() => {
          setOpen(true);
          if (trial) setStage("done");
        }}
      >
        {label}
      </button>

      {open && (
        <div
          className="fixed inset-0 z-[100] bg-ink/60 flex items-center
                     justify-center p-5 animate-fade"
          onClick={(e) => {
            if (e.target === e.currentTarget && stage !== "running") setOpen(false);
          }}
        >
          <div
            className="w-full max-w-[520px] bg-paper text-ink border-3 border-ink
                       shadow-brut-lg max-h-[90vh] flex flex-col animate-pop"
            role="dialog"
            aria-modal="true"
          >
            <div className="bg-ink text-bone px-4 py-3 flex justify-between items-center text-sm">
              <b>Free scan</b>
              <button
                className="bg-transparent border-0 text-bone text-[17px] cursor-pointer
                           leading-none px-1 py-0.5 font-[inherit]
                           disabled:opacity-35 disabled:cursor-not-allowed"
                onClick={() => setOpen(false)}
                disabled={stage === "running"}
                aria-label="Close"
              >
                ✕
              </button>
            </div>

            <div className="p-[22px] overflow-y-auto max-[560px]:p-[18px]">
              <h2 className="text-h3 mb-2">Upload your resume</h2>
              <p className="text-[13.5px] font-semibold opacity-70 mb-[18px]">
                No account, no card. We read it once to score live postings
                against it, and we don&rsquo;t keep the file.
              </p>

              {err && <div className={ALERT}>{err}</div>}

              {stage !== "done" && (
                <>
                  {/* Jade on a chosen file and on hover: picking a file is the
                      step going right, so it gets the positive colour rather
                      than the action colour the Start button already owns. */}
                  <div
                    className={`border-3 border-dashed border-ink text-center
                                px-5 py-[30px] transition-colors duration-100
                                ${over || file ? "bg-jade" : "bg-paper hover:bg-jade"}
                                ${stage === "running" ? "cursor-default" : "cursor-pointer"}`}
                    onClick={() => stage !== "running" && inputRef.current?.click()}
                    onDragOver={(e) => {
                      e.preventDefault();
                      setOver(true);
                    }}
                    onDragLeave={() => setOver(false)}
                    onDrop={(e) => {
                      e.preventDefault();
                      setOver(false);
                      if (stage === "running") return;
                      const f = e.dataTransfer.files?.[0];
                      if (f) pick(f);
                    }}
                  >
                    {stage === "running" ? (
                      <>
                        <span className={SPINNER} />
                        <b>Scanning live postings…</b>
                        <div className="text-[12.5px] font-semibold opacity-70 mt-1.5">
                          Scoring every one against your resume
                        </div>
                      </>
                    ) : file ? (
                      <>
                        <b className="text-[15px] block">{file.name}</b>
                        <span className="text-[12.5px] font-semibold opacity-75">
                          Ready — click Start. Or choose a different file.
                        </span>
                      </>
                    ) : (
                      <>
                        <b className="text-base block mb-[5px]">
                          Drop your resume here
                        </b>
                        <span className="text-[12.5px] font-semibold opacity-70">
                          or click to choose · PDF, DOCX, TXT · max 8MB
                        </span>
                      </>
                    )}
                  </div>
                  <input
                    ref={inputRef}
                    type="file"
                    accept=".pdf,.docx,.txt,.md"
                    hidden
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) pick(f);
                    }}
                  />
                </>
              )}

              {stage === "done" && trial && (
                <div className="border-3 border-ink bg-bone text-ink p-6">
                  <b className="text-[15px] block mb-1.5">Scan complete</b>
                  <p className="text-[13.5px] font-semibold">
                    {trial.summary.matches} match
                    {trial.summary.matches === 1 ? "" : "es"} and{" "}
                    {trial.summary.near_misses} near-miss
                    {trial.summary.near_misses === 1 ? "" : "es"} out of{" "}
                    {trial.summary.pool.toLocaleString()} live postings.
                  </p>
                </div>
              )}
            </div>

            <div
              className="border-t-3 border-ink px-[22px] py-4 flex items-center
                         justify-between gap-3.5 flex-wrap bg-bone
                         max-[560px]:px-[18px] max-[560px]:py-3.5"
            >
              {stage === "done" ? (
                <>
                  <p className="text-[12.5px] font-semibold opacity-80 max-w-[30ch] leading-[1.45] max-[560px]:max-w-none">
                    Free scan — you can open <b>one</b> result. The rest stay
                    locked until you start a plan.
                  </p>
                  <button
                    className="btn btn-ink ml-auto max-[560px]:ml-0 max-[560px]:w-full max-[560px]:text-center"
                    onClick={reveal}
                  >
                    See results
                  </button>
                </>
              ) : (
                <button
                  className="btn ml-auto max-[560px]:ml-0 max-[560px]:w-full"
                  onClick={start}
                  disabled={stage !== "ready"}
                >
                  {stage === "running" && <span className={SPINNER} />}
                  {stage === "running" ? "Scanning…" : "Start"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Results are portalled out of the hero so they cannot inherit its
          bone text colour, and so they span the page rather than sitting in
          one column of the hero grid. */}
      {trial && !open && mount
        ? createPortal(<TrialResults trial={trial} />, mount)
        : null}
    </>
  );
}

function TrialResults({ trial }: { trial: Trial }) {
  const s = trial.summary;

  if (trial.empty) {
    return (
      <section className="band bg-bone text-ink">
        <div className="wrap">
          <h2 className="text-h2 mb-3">
            Nothing matched today — and that&rsquo;s worth knowing.
          </h2>
          <p className="lede mb-5">
            We scored {s.scored.toLocaleString()} postings against your resume
            and {s.near_misses} came close without clearing the bar. That
            usually means the filters are narrow rather than the market being
            empty. A plan shows you exactly what blocked each one.
          </p>
          <Link href="/#plans" className="btn btn-ink">
            See plans
          </Link>
        </div>
      </section>
    );
  }

  const v = trial.visible!;
  const locked = trial.locked || [];

  return (
    <section className="band bg-bone text-ink">
      <div className="wrap">
        <span className="eyebrow">Your free scan</span>
        <h2 className="text-h2 mt-[18px] mb-2.5">
          {s.matches} match{s.matches === 1 ? "" : "es"} found.
        </h2>
        <p className="lede mb-6">
          From {s.pool.toLocaleString()} live postings, scored against{" "}
          {s.skills} skills, {s.years} years and your location. One is open
          below — the rest are locked.
        </p>

        <div className={`${G4} mb-[30px]`}>
          <div className={`${STAT} bg-lime`}>
            <b className={STAT_N}>{s.matches}</b>
            <span className={STAT_L}>Matches</span>
          </div>
          <div className={`${STAT} bg-sun`}>
            <b className={STAT_N}>{s.near_misses}</b>
            <span className={STAT_L}>Came close</span>
          </div>
          <div className={`${STAT} bg-paper`}>
            <b className={STAT_N}>{s.scored.toLocaleString()}</b>
            <span className={STAT_L}>Scored for you</span>
          </div>
          <div className={`${STAT} bg-jade`}>
            <b className={STAT_N}>{s.skills}</b>
            <span className={STAT_L}>Skills read</span>
          </div>
        </div>

        <div className="sechead bg-jade">
          <h2 className="text-xl">Your top match</h2>
          <em className="not-italic text-[12.5px] font-semibold opacity-80">
            Open it — this one is yours for free
          </em>
        </div>

        <JobCard job={v as any} expanded emphasis />

        {locked.length > 0 && (
          <>
            {/* Sun, not flare: locked results are a limit you have hit, which
                is the same category as a blocker — not a call to action. */}
            <div className="sechead bg-sun">
              <h2 className="text-xl">Locked — {trial.locked_total}</h2>
              <em className="not-italic text-[12.5px] font-semibold opacity-80">
                Real matches, held back on the free scan
              </em>
            </div>

            {/* The blur is presentation only. There is nothing behind it to
                recover — the API sends bar widths, never the withheld jobs —
                so devtools, "view source" and the network tab all show the
                same nothing. */}
            <div className="relative">
              <div
                aria-hidden="true"
                className="blur-[6px] opacity-55 pointer-events-none select-none"
              >
                {locked.map((l, i) => (
                  <div
                    className="border-3 border-ink bg-paper shadow-brut-sm
                               px-[18px] py-4 mb-3 pointer-events-none select-none"
                    key={i}
                  >
                    <div className="flex justify-between gap-3.5 items-start">
                      <div className="flex-1">
                        <span
                          className="block bg-ink opacity-30 rounded-sm"
                          style={{ width: `${l.bars[0] * 100}%`, height: 15 }}
                        />
                        <span
                          className="block bg-ink rounded-sm"
                          style={{
                            width: `${l.bars[1] * 100}%`,
                            height: 11,
                            marginTop: 9,
                            opacity: 0.18,
                          }}
                        />
                      </div>
                      <span className="border-2 border-ink bg-jade text-transparent text-xs font-extrabold px-2.5 py-[3px]">
                        00
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              <div className="absolute inset-0 flex items-center justify-center p-5">
                <div className="bg-paper border-3 border-ink shadow-brut-lg px-7 py-[26px] max-w-[430px] text-center max-[560px]:p-5">
                  <b className="text-[19px] block mb-2">
                    {trial.locked_total} more match
                    {trial.locked_total === 1 ? "" : "es"} waiting
                  </b>
                  <p className="text-sm font-semibold mb-4">
                    Plus the roles that came close, each with the exact reason
                    it didn&rsquo;t clear. Start a plan to see all of them and
                    get a fresh list every morning.
                  </p>
                  <Link href="/#plans" className="btn btn-ink">
                    Unlock all {s.matches} matches →
                  </Link>
                  <p className="text-xs opacity-70 mt-3 font-semibold">
                    Plans are free while payments are switched off.
                  </p>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
