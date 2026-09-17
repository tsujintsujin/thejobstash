"use client";

import { useRef, useState } from "react";
import { MAX_YEARS, levelFromYears } from "@/lib/experience";

/**
 * The Experience and Seniority cells of the attribute grid, together because
 * seniority follows the years. Optimistic like WorkSetupSelect; clicks are
 * batched so a run of + presses saves once, and a failed save puts back the
 * last value that did save.
 */
export default function ExperienceCounter({
  initialYears,
  initialLevel,
  cell,
  label,
  value,
}: {
  initialYears: number | null;
  initialLevel: string;
  cell: string;
  label: string;
  value: string;
}) {
  const [years, setYears] = useState(initialYears);
  const [level, setLevel] = useState(initialLevel);
  const [err, setErr] = useState("");
  const saved = useRef({ years: initialYears, level: initialLevel });
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  function step(by: number) {
    const next = Math.min(MAX_YEARS, Math.max(0, (years ?? 0) + by));
    if (next === years) return;
    setYears(next);
    setLevel(levelFromYears(next));
    setErr("");
    clearTimeout(timer.current);
    timer.current = setTimeout(() => save(next), 500);
  }

  async function save(next: number) {
    const r = await fetch("/api/experience", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ years: next }),
    }).catch(() => null);
    if (r?.ok) {
      saved.current = { years: next, level: levelFromYears(next) };
    } else {
      setYears(saved.current.years);
      setLevel(saved.current.level);
      setErr("Couldn't save. Try again.");
    }
  }

  const btn =
    "w-9 h-9 flex-none grid place-items-center border-2 border-ink bg-paper " +
    "text-[20px] font-extrabold leading-none cursor-pointer hover:bg-ink " +
    "hover:text-paper disabled:opacity-30 disabled:pointer-events-none";

  return (
    <>
      <div className={cell}>
        <span className={label}>Experience</span>
        <div className="flex items-center gap-2.5 mt-[3px]">
          <button
            type="button"
            className={btn}
            aria-label="One year less"
            disabled={!years}
            onClick={() => step(-1)}
          >
            −
          </button>
          <b className={`${value} !mt-0 min-w-[4.5ch] text-center`} aria-live="polite">
            {years ?? "—"} {years === 1 ? "yr" : "yrs"}
          </b>
          <button
            type="button"
            className={btn}
            aria-label="One year more"
            disabled={years === MAX_YEARS}
            onClick={() => step(1)}
          >
            +
          </button>
        </div>
        {err && <span className="text-[12px] font-bold block mt-1">{err}</span>}
      </div>
      <div className={cell}>
        <span className={label}>Seniority</span>
        <b className={`${value} capitalize`}>{level}</b>
      </div>
    </>
  );
}
