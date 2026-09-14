import Link from "next/link";
import { SECHEAD_NOTE } from "@/app/ui";

/**
 * Chrome shared by /privacy and /terms.
 *
 * Two pages that are 95% identical would drift the moment one of them was
 * edited, so the header, the section rule and the prose measure live here and
 * only the words live in the pages.
 *
 * No new colours and no new primitives. The header is the footer's ink, the
 * section headings are the same `.sechead` block the dashboard uses, and the
 * summary card is jade because "we do not sell this" is good news, which is
 * the one thing that token is for.
 */

/* Everything that names a human, in one place. A policy that repeats an
   address in nine paragraphs is nine edits when it changes.
   >>> Swap these for the live details before the site goes public. <<< */
export const OPERATOR = "TSUJIN IT SOLUTIONS";
export const CONTACT_EMAIL = "thejobstash@gmail.com";
export const EFFECTIVE = "14 September 2026";

export type Section = {
  id: string;
  title: string;
  body: React.ReactNode;
};

/* 68ch, not the 60ch of `.lede`. A lede is three lines and wants to be
   narrow; this is four thousand words and a short measure turns it into a
   column of ragged stubs. */
const MEASURE = "max-w-[68ch]";

export function P({ children }: { children: React.ReactNode }) {
  return (
    <p className={`${MEASURE} text-[15px] leading-[1.62] mb-[13px]`}>
      {children}
    </p>
  );
}

/** A definition-style list: the bold term is the thing, the rest explains it. */
export function Rows({ rows }: { rows: [string, React.ReactNode][] }) {
  return (
    <ul className={`${MEASURE} mb-[13px] grid gap-[9px]`}>
      {rows.map(([term, detail]) => (
        <li
          key={term}
          className="border-l-3 border-ink pl-[13px] text-[15px] leading-[1.55]"
        >
          <strong className="font-extrabold">{term}</strong>
          {detail ? <> — {detail}</> : null}
        </li>
      ))}
    </ul>
  );
}

export function Note({ children }: { children: React.ReactNode }) {
  return (
    <div
      className={`${MEASURE} border-3 border-ink bg-sun shadow-brut-sm
                  px-[15px] py-[13px] text-sm leading-[1.55] font-semibold
                  mb-[15px]`}
    >
      {children}
    </div>
  );
}

export function LegalHeader({
  title,
  lede,
}: {
  title: string;
  lede: string;
}) {
  return (
    <section className="band band-tight bg-ink text-bone">
      <div className="wrap">
        <span className="eyebrow text-ink">Legal</span>
        <h1 className="text-h2 mt-[18px] mb-3">{title}</h1>
        <p className="lede opacity-85">{lede}</p>
        <p className="text-[12px] font-extrabold uppercase tracking-[0.09em]
                      opacity-60 mt-5">
          In effect {EFFECTIVE}
        </p>
      </div>
    </section>
  );
}

/**
 * The body. Contents list and sections are rendered from the same array, so a
 * renamed heading can never leave a dead anchor behind it.
 */
export function LegalBody({
  summary,
  sections,
  otherHref,
  otherLabel,
}: {
  summary: React.ReactNode;
  sections: Section[];
  otherHref: string;
  otherLabel: string;
}) {
  return (
    <section className="band bg-bone">
      <div className="wrap">
        <div className="max-w-[820px]">
          <div className="card bg-jade shadow-brut mb-9">
            <h2 className="text-h3 mb-3">The short version</h2>
            <div className="text-[15px] leading-[1.6]">{summary}</div>
            <p className="text-[12px] font-bold opacity-70 mt-4">
              This box is a summary and is not the agreement. The numbered
              sections below are.
            </p>
          </div>

          <nav aria-label="Contents" className="mb-10">
            <h2 className="text-[11px] font-extrabold uppercase
                           tracking-[0.12em] opacity-70 mb-[10px]">
              Contents
            </h2>
            <ol className="flex flex-wrap gap-[7px] list-none p-0 m-0">
              {sections.map((s, i) => (
                <li key={s.id}>
                  <a href={`#${s.id}`} className="tag no-underline hover:bg-sun">
                    {i + 1}. {s.title}
                  </a>
                </li>
              ))}
            </ol>
          </nav>

          {sections.map((s, i) => (
            /* scroll-mt clears the 68px sticky nav; without it every anchor
               lands with its own heading hidden behind the header. */
            <section key={s.id} id={s.id} className="scroll-mt-[84px]">
              <div className="sechead bg-paper">
                <h2 className="text-h3">{s.title}</h2>
                <em className={SECHEAD_NOTE}>
                  {String(i + 1).padStart(2, "0")}
                </em>
              </div>
              {s.body}
            </section>
          ))}

          <p className="border-t-3 border-ink mt-11 pt-5 text-sm font-bold">
            Also worth reading:{" "}
            <Link href={otherHref} className="underline">
              {otherLabel}
            </Link>
            . Questions about either:{" "}
            <a href={`mailto:${CONTACT_EMAIL}`} className="underline">
              {CONTACT_EMAIL}
            </a>
            .
          </p>
        </div>
      </div>
    </section>
  );
}
