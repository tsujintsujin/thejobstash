"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ALERT, G3, SPINNER } from "../ui";

/* Only the recommended plan wears an accent — three coloured cards would rank
   nothing. Jade because it is a recommendation, not a warning. */
const PLANS = [
  { id: "one_time", name: "One sweep", days: "1 day", bg: "bg-paper" },
  { id: "three_day", name: "Three days", days: "3 days", bg: "bg-jade" },
  { id: "seven_day", name: "Seven days", days: "7 days", bg: "bg-paper" },
];

export default function PlanPicker() {
  const router = useRouter();
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");

  async function start(plan: string) {
    setErr("");
    setBusy(plan);
    const r = await fetch("/api/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan }),
    });
    const j = (await r.json()) as any;
    setBusy("");
    if (!r.ok) return setErr(j.error || "Couldn't start that plan.");
    router.refresh();
  }

  return (
    <>
      {err && <div className={ALERT}>{err}</div>}
      <div className={`${G3} mb-2.5`}>
        {PLANS.map((p) => (
          <div key={p.id} className={`card ${p.bg}`}>
            <b className="text-[17px]">{p.name}</b>
            <p className="text-[13px] font-semibold opacity-70 mt-1 mb-3.5">
              {p.days} of digests · free
            </p>
            <button
              className="btn btn-ink btn-sm"
              onClick={() => start(p.id)}
              disabled={!!busy}
            >
              {busy === p.id && <span className={SPINNER} />}
              {busy === p.id ? "Starting…" : "Start"}
            </button>
          </div>
        ))}
      </div>
    </>
  );
}
