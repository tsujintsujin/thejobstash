"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import JobCard, { type Job } from "../JobCard";
import {
  ALERT,
  ALERT_INFO,
  ALERT_OK,
  G4,
  SECHEAD_NOTE,
  STAT,
  STAT_L,
  STAT_N,
} from "../ui";

type Digest = {
  sections: Record<string, Job[]>;
  summary: {
    matches: number;
    near_misses: number;
    pool_size: number;
    scored: number;
    thin: boolean;
    first_ever: boolean;
    backfilled: number;
    reserve_left: number;
    blocker_copy: string[];
  };
};

/* The quality ladder, and the one place in the product where colour is doing
   real work. It descends by value rather than rotating through hues: the
   positive accent, then two neutrals of decreasing brightness, then the
   attention accent at the bottom.

   The old build ran sky → peach → paper → coral, which put the loudest colour
   it had on the WORST tier and used the primary-button colour to do it. */
const SECTIONS: [string, string, string, string][] = [
  ["strong", "Strong matches", "bg-jade", "Worth applying to today."],
  ["worth_a_look", "Worth a look", "bg-paper", "Solid fits with a caveat or two."],
  ["stretch", "Stretch", "bg-bone", "Below your usual bar — shown because the day was quiet."],
  ["near_miss", "Came close", "bg-sun", "Matched your work, blocked by one thing."],
];

export default function DigestPanel({
  hasProfile,
  hasPlan,
  deliveredToday,
}: {
  hasProfile: boolean;
  hasPlan: boolean;
  deliveredToday: boolean;
}) {
  const router = useRouter();
  const [digest, setDigest] = useState<Digest | null>(null);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");

  async function run(preview: boolean) {
    setErr("");
    setBusy(preview ? "preview" : "send");
    const r = await fetch(`/api/deliver${preview ? "?preview=1" : ""}`, {
      method: "POST",
    });
    const j = (await r.json()) as any;
    setBusy("");
    if (!r.ok) return setErr(j.error || "Something went wrong.");
    if (preview) {
      setDigest(j);
    } else {
      // A real delivery writes rows the server component renders, so the page
      // has to re-fetch rather than patch state locally.
      router.refresh();
      setDigest(null);
    }
  }

  if (!hasProfile) {
    return (
      <div className="border-3 border-ink bg-bone text-ink p-6">
        <p className="text-sm font-semibold">
          Upload a resume and your matches will appear here.
        </p>
      </div>
    );
  }

  return (
    <>
      {err && <div className={ALERT}>{err}</div>}

      {digest && (
        <>
          <div className={`${G4} mb-5`}>
            <div className={`${STAT} bg-paper`}>
              <b className={STAT_N}>{digest.summary.matches}</b>
              <span className={STAT_L}>Matches</span>
            </div>
            <div className={`${STAT} bg-paper`}>
              <b className={STAT_N}>{digest.summary.near_misses}</b>
              <span className={STAT_L}>Came close</span>
            </div>
            <div className={`${STAT} bg-paper`}>
              <b className={STAT_N}>{digest.summary.scored.toLocaleString()}</b>
              <span className={STAT_L}>Scored for you</span>
            </div>
            <div className={`${STAT} bg-paper`}>
              <b className={STAT_N}>{digest.summary.reserve_left}</b>
              <span className={STAT_L}>Held in reserve</span>
            </div>
          </div>

          {digest.summary.thin && (
            <div className={ALERT_INFO}>
              Quiet day. Rather than pad this out with roles that don&rsquo;t
              fit, here&rsquo;s everything that genuinely did — and what came
              close. A real delivery would add a day to your plan.
            </div>
          )}

          {digest.summary.backfilled > 0 && (
            <div className={ALERT_OK}>
              {digest.summary.backfilled} of these were held back from earlier
              sweeps so today wouldn&rsquo;t come up short.
            </div>
          )}

          {SECTIONS.map(([key, title, colour, blurb]) => {
            const rows = digest.sections[key] || [];
            if (!rows.length) return null;
            return (
              <div key={key}>
                <div className={`sechead ${colour}`}>
                  <h2 className="text-xl">
                    {title} — {rows.length}
                  </h2>
                  <em className={SECHEAD_NOTE}>{blurb}</em>
                </div>
                {rows.map((j) => (
                  <JobCard
                    key={j.fp}
                    job={j}
                    showBlockers={key === "near_miss"}
                  />
                ))}
              </div>
            );
          })}

          {digest.summary.blocker_copy.length > 0 && (
            <div className="card bg-ink text-bone mt-6">
              <h2 className="text-h3 mb-3">
                What&rsquo;s standing in your way
              </h2>
              <ul className="list-none">
                {digest.summary.blocker_copy.map((c) => (
                  <li
                    key={c}
                    className="text-sm font-semibold py-1.5 border-b border-bone-line last:border-b-0"
                  >
                    {c}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {digest.summary.matches === 0 &&
            digest.summary.near_misses === 0 && (
              <div className="border-3 border-ink bg-bone text-ink p-6">
                <p className="text-sm font-semibold">
                  Nothing left in the pool you haven&rsquo;t already been shown.
                  Tomorrow&rsquo;s sweep brings roughly a thousand new postings.
                </p>
              </div>
            )}
        </>
      )}
    </>
  );
}
