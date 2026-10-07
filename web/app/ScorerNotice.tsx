"use client";

import { useEffect, useState } from "react";

/**
 * Asks /api/scorer once and reports the answer: null while asking, then
 * true/false. Uploads and runs need the home machine, so when it is down the
 * site says so up front instead of failing after a file is picked.
 */
export function useScorerUp() {
  const [up, setUp] = useState<boolean | null>(null);
  useEffect(() => {
    fetch("/api/scorer", { cache: "no-store" })
      .then((r) => r.json() as Promise<{ up: boolean }>)
      .then((j) => setUp(j.up === true))
      .catch(() => setUp(false));
  }, []);
  return up;
}

export function ScorerDownNote({ className = "" }: { className?: string }) {
  return (
    <div
      role="status"
      className={`border-3 border-ink bg-sun text-ink px-[15px] py-[13px]
                  text-sm font-bold ${className}`}
    >
      We&rsquo;re upgrading our matching AI right now. Resume uploads are
      paused while we improve it &mdash; please check back shortly.
    </div>
  );
}

/** The note, shown only when the scorer is down. */
export default function ScorerNotice({ className = "" }: { className?: string }) {
  return useScorerUp() === false ? <ScorerDownNote className={className} /> : null;
}
