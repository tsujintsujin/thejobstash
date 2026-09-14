"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ALERT, ALERT_OK, SPINNER } from "./ui";

type Diag = {
  skills_found: number;
  top_skills: string[];
  years: number | null;
  total_years: number | null;
  level: string;
  families: string[];
  country: string;
  text_chars: number;
};

const READOUT_K =
  "text-[11px] font-extrabold opacity-70 uppercase tracking-[0.08em]";
const READOUT_V = "text-[26px] font-extrabold block mt-1";
const READOUT_NOTE = "text-[12.5px] font-semibold opacity-70";

export default function UploadCard({ inModal = false }: { inModal?: boolean }) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [over, setOver] = useState(false);
  const [diag, setDiag] = useState<Diag | null>(null);
  const [name, setName] = useState("");

  async function upload(file: File) {
    setErr("");
    setDiag(null);
    setBusy(true);
    setName(file.name);
    const fd = new FormData();
    fd.append("resume", file);
    const r = await fetch("/api/resume", { method: "POST", body: fd });
    const j = (await r.json()) as any;
    setBusy(false);
    if (!r.ok) return setErr(j.error || "Couldn't read that file.");
    setDiag(j.diagnostics);
  }

  const card = (
    <div className="card shadow-brut-lg">
      {/* The row the step counter used to occupy, now holding the way out.
          Kept as its own row so the heading keeps the full width it had -
          sharing a line with the button crowded it. A dialog has its own
          close button, so the row goes there. */}
      {!inModal && (
        <div className="flex justify-end">
          <Link href="/dashboard" className="btn btn-paper btn-sm">
            Back
          </Link>
        </div>
      )}
      <h1 className="text-h2 mt-[18px] mb-2">Upload your resume</h1>
      <p className="text-sm font-semibold opacity-70 mb-6">
        PDF, DOCX or plain text. We read it once to build your matching
        profile — it&rsquo;s never shared with employers.{" "}
        {/* The claim above is the one worth being able to check, so it
            links to the section that spells it out rather than asking
            anyone to take it on trust. */}
        <Link href="/privacy#resume" className="underline">
          What happens to your file
        </Link>
        .
      </p>

      {err && <div className={ALERT}>{err}</div>}

      {!diag && (
        <>
          <div
            className={`border-3 border-dashed border-ink text-center
                        px-6 py-[44px] cursor-pointer transition-colors
                        duration-100 ${over ? "bg-jade" : "bg-paper hover:bg-jade"}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setOver(true);
            }}
            onDragLeave={() => setOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setOver(false);
              const f = e.dataTransfer.files?.[0];
              if (f) upload(f);
            }}
          >
            {busy ? (
              <>
                <span className={SPINNER} />
                <b>Reading {name}…</b>
              </>
            ) : (
              <>
                <b className="text-[17px] block mb-1.5">
                  Drop your resume here
                </b>
                <span className="text-[13.5px] font-semibold opacity-70">
                  or click to choose a file · max 8MB
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
              if (f) upload(f);
            }}
          />
        </>
      )}

      {diag && (
        <>
          <div className={ALERT_OK}>
            Read {diag.text_chars.toLocaleString()} characters from{" "}
            <b>{name}</b>. Here&rsquo;s what we understood — check it looks
            right.
          </div>

          <div className="grid gap-4 grid-cols-2 max-[620px]:grid-cols-1 mb-[18px]">
            <div className="border-3 border-ink bg-bone text-ink p-6">
              <span className={READOUT_K}>Experience</span>
              <b className={READOUT_V}>{diag.years ?? "—"} yrs</b>
              <span className={READOUT_NOTE}>
                relevant
                {diag.total_years && diag.total_years !== diag.years
                  ? ` · ${diag.total_years} total incl. other fields`
                  : ""}
              </span>
            </div>
            <div className="border-3 border-ink bg-bone text-ink p-6">
              <span className={READOUT_K}>Level / based in</span>
              <b className={`${READOUT_V} capitalize`}>{diag.level}</b>
              <span className={`${READOUT_NOTE} capitalize`}>
                {diag.country}
              </span>
            </div>
          </div>

          <div className="mb-6">
            <label>Skills found ({diag.skills_found})</label>
            <div className="flex gap-1.5 flex-wrap">
              {diag.top_skills.map((s) => (
                <span key={s} className="tag">
                  {s}
                </span>
              ))}
            </div>
            {diag.skills_found < 5 && (
              <p className="text-[12.5px] font-semibold opacity-70 mt-1.5">
                That&rsquo;s a short list — a resume with a clear skills
                section usually matches better.
              </p>
            )}
          </div>

          <div className="flex gap-2.5 flex-wrap">
            <button
              className="btn btn-ink"
              onClick={() => {
                router.push("/dashboard");
                router.refresh();
              }}
            >
              Looks right — see my matches
            </button>
            <button
              className="btn btn-paper"
              onClick={() => {
                setDiag(null);
                setName("");
              }}
            >
              Try a different file
            </button>
          </div>
        </>
      )}
    </div>
  );

  if (inModal) return card;

  /* Sun: this page is a prerequisite you have not finished yet, which is the
     same category the dashboard uses sun for. */
  return (
    <main className="band band-solo bg-sun">
      <div className="narrow">{card}</div>
    </main>
  );
}
