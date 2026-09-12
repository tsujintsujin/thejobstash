"use client";

/**
 * One job, everywhere it appears.
 *
 * Extraction from scraped prose is lossy - across the live pool, roughly half
 * of postings yield responsibilities and a quarter yield requirements, so
 * every section here is conditional. The card has to read properly when all
 * that came back was a title and a summary, which is the common case.
 *
 * Salary is the exception: it always renders. "Salary undisclosed" is
 * information, and a blank where the money should be just looks broken.
 */
export type Job = {
  fp?: string;
  title: string;
  company: string;
  location: string;
  url: string;
  source: string;
  score: number;
  salary: string;
  salary_known?: boolean;
  summary?: string | null;
  responsibilities?: string[];
  requirements?: string[];
  reasons?: string[];
  blockers?: { kind: string; detail: string }[];
};

const LIST_H =
  "text-[10.5px] font-extrabold uppercase tracking-[0.09em] opacity-65 mb-[7px]";
/* A square, not a disc: the system has no round edges anywhere else. */
const LIST_LI =
  "text-[13px] leading-normal py-1 pl-[15px] relative " +
  "before:content-[''] before:absolute before:left-0 before:top-[11px] " +
  "before:w-1.5 before:h-1.5 before:bg-ink";

export default function JobCard({
  job,
  showBlockers = false,
  expanded = false,
  emphasis = false,
}: {
  job: Job;
  showBlockers?: boolean;
  expanded?: boolean;
  emphasis?: boolean;
}) {
  const why = showBlockers && job.blockers?.length
    ? job.blockers.map((b) => b.detail).join("; ")
    : (job.reasons || []).slice(0, 2).join("; ");

  const resp = job.responsibilities || [];
  const reqs = job.requirements || [];
  const hasDetail = resp.length > 0 || reqs.length > 0;

  /* The chip and the reason rail carry the verdict, so the card says which
     pile it came from before you read a word of it. Jade for a match, sun for
     one that was blocked - never flare, which on this page only ever means
     "press me". */
  const verdict = showBlockers ? "bg-sun" : "bg-jade";
  const rail = showBlockers ? "border-sun" : "border-ink";

  const lists = (
    <>
      {resp.length > 0 && (
        <div className="mt-[13px]">
          <h4 className={LIST_H}>What you&rsquo;d be doing</h4>
          <ul className="list-none">
            {resp.map((r, i) => (
              <li key={i} className={LIST_LI}>{r}</li>
            ))}
          </ul>
        </div>
      )}
      {reqs.length > 0 && (
        <div className="mt-[13px]">
          <h4 className={LIST_H}>What they&rsquo;re asking for</h4>
          <ul className="list-none">
            {reqs.map((r, i) => (
              <li key={i} className={LIST_LI}>{r}</li>
            ))}
          </ul>
        </div>
      )}
    </>
  );

  return (
    <div
      className={`border-3 border-ink bg-paper text-ink px-[18px] py-4 mb-3 ${
        emphasis ? "shadow-brut" : "shadow-brut-sm"
      }`}
    >
      <div className="flex justify-between gap-3.5 items-start">
        <h3 className="text-[17px]">
          <a
            href={job.url}
            target="_blank"
            rel="noreferrer"
            className="no-underline hover:underline"
          >
            {job.title}
          </a>
        </h3>
        <span
          className={`border-2 border-ink text-ink text-xs font-extrabold
                      px-2.5 py-[3px] whitespace-nowrap ${verdict}`}
        >
          {job.score}
        </span>
      </div>

      <div className="text-[13.5px] font-semibold mt-1.5">
        <b className="font-extrabold">{job.company || "Unknown company"}</b>
        <span
          className={
            "before:content-['·'] before:mx-1.5 before:opacity-45 " +
            (job.salary_known
              ? "font-bold"
              : "opacity-60 font-semibold italic")
          }
        >
          {job.salary || "Salary undisclosed"}
        </span>
      </div>

      <div className="text-xs opacity-70 mt-1 font-semibold">
        {job.location || "Location not stated"} · via {job.source}
      </div>

      {why && (
        <div className={`mt-2.5 border-l-4 pl-2.5 py-1 text-[13px] font-semibold ${rail}`}>
          {why}
        </div>
      )}

      {job.summary && (
        <p className="text-[13.5px] leading-[1.55] mt-[11px] opacity-90">
          {job.summary}
        </p>
      )}

      {hasDetail &&
        (expanded ? (
          lists
        ) : (
          <details className="group mt-3 border-t-2 border-ink-line pt-2.5">
            <summary
              className="text-xs font-extrabold cursor-pointer list-none uppercase
                         tracking-[0.07em] opacity-70 hover:opacity-100
                         group-open:opacity-100
                         after:content-['▾'] after:ml-1
                         group-open:after:content-['▴']"
            >
              Role details
              {resp.length > 0 && ` · ${resp.length} responsibilit${resp.length === 1 ? "y" : "ies"}`}
              {reqs.length > 0 && ` · ${reqs.length} requirement${reqs.length === 1 ? "" : "s"}`}
            </summary>
            {lists}
          </details>
        ))}

      <div className="mt-3">
        <a
          href={job.url}
          target="_blank"
          rel="noreferrer"
          className="btn btn-sm btn-paper"
        >
          Open the posting →
        </a>
      </div>
    </div>
  );
}
