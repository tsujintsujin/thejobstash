"use client";

import { useState } from "react";
import { WORK_SETUPS, WORK_SETUP_LABEL, WorkSetup } from "@/lib/workSetup";

/**
 * Remote / hybrid / onsite. Optimistic like SkillToggles: the choice shows
 * at once, and a failed write puts the old one back.
 */
export default function WorkSetupSelect({ initial }: { initial: WorkSetup }) {
  const [value, setValue] = useState<WorkSetup>(initial);
  const [err, setErr] = useState("");

  async function change(next: WorkSetup) {
    const prev = value;
    setValue(next);
    setErr("");
    const r = await fetch("/api/work-setup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ setup: next }),
    }).catch(() => null);
    if (!r?.ok) {
      setValue(prev);
      setErr("Couldn't save. Try again.");
    }
  }

  return (
    <>
      <select
        aria-label="Work setup"
        value={value}
        onChange={(e) => change(e.target.value as WorkSetup)}
        /* Same type as the facts beside it; the dashed rule and the arrow
           are the only hint that this one can be changed. */
        className="w-full bg-transparent border-0 border-b-2 border-dashed
                   border-ink p-0 text-[19px] leading-[1.45] font-extrabold
                   tracking-[-0.02em] cursor-pointer focus:outline-2
                   focus:outline-offset-2"
      >
        {WORK_SETUPS.map((s) => (
          <option key={s} value={s}>
            {WORK_SETUP_LABEL[s]}
          </option>
        ))}
      </select>
      {err && <span className="text-[12px] font-bold block mt-1">{err}</span>}
    </>
  );
}
