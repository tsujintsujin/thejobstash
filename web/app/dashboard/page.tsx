import Link from "next/link";
import { redirect } from "next/navigation";
import { currentUser } from "@/lib/session";
import { deliveriesFor, openRunFor, profileFor } from "@/lib/db";
import DigestPanel from "./DigestPanel";
import DeleteDigest from "./DeleteDigest";
import BuyCredits from "./BuyCredits";
import SkillToggles from "./SkillToggles";
import WorkSetupSelect from "./WorkSetupSelect";
import ExperienceCounter from "./ExperienceCounter";
import { workSetupOf, WORK_SETUP_LABEL, type WorkSetup } from "@/lib/workSetup";
import { STAT, STAT_L, STAT_N } from "../ui";

export const dynamic = "force-dynamic";

/* The attribute grid. One ink background showing through 1px gaps, so the
   rules between cells are the same ink as every other border on the page
   rather than a grey table line. */
const FACTS =
  "grid gap-px bg-ink border-2 border-ink mb-4 grid-cols-3 " +
  "max-[760px]:grid-cols-2 max-[460px]:grid-cols-1";
const FACT = "bg-paper px-[13px] py-[11px]";
/* .68, not .55: measured 3.9:1 against white at 10px, which is under AA. */
const FACT_K =
  "block text-[10px] font-extrabold uppercase tracking-[0.09em] opacity-70";
const FACT_V =
  "block text-[19px] font-extrabold mt-[3px] tracking-[-0.02em]";

/* One box per section of a digest, written by render.py into summary_json.
   A row from before the boxes existed has none, and falls back to View. */
type Part = { key: string; count: number; label: string; colour: string; pdf?: boolean };

/* The settings a run was scored with, written by delivery.py into
   summary_json.profile. A row from before those fields existed has no name or
   setup, and the caller falls back to the profile as it stands now. */
function settingsOf(summaryJson: unknown): {
  name?: string;
  years?: number | null;
  setup?: string;
} {
  if (typeof summaryJson !== "string") return {};
  try {
    return JSON.parse(summaryJson)?.profile ?? {};
  } catch {
    return {};
  }
}

function partsOf(summaryJson: unknown): Part[] {
  if (typeof summaryJson !== "string") return [];
  try {
    const p = JSON.parse(summaryJson)?.parts;
    /* Shape-checked rather than trusted: this is the only place a rendered
       digest's own JSON reaches the page, and a half-written row must degrade
       to "no boxes" instead of throwing the whole dashboard. */
    return Array.isArray(p)
      ? p.filter(
          (x: Part) =>
            x && typeof x.key === "string" && typeof x.label === "string" &&
            typeof x.colour === "string" && Number.isFinite(x.count)
        )
      : [];
  } catch {
    return [];
  }
}

export default async function Dashboard() {
  const user = await currentUser();
  if (!user) redirect("/signup?mode=signin");

  // Independent reads, so they go together rather than one after the other -
  // each is a network round trip to D1 now, not a local file read.
  const [profile, deliveries, openRun] = await Promise.all([
    profileFor(user.id),
    deliveriesFor(user.id),
    openRunFor(user.id),
  ]);
  const parsed = profile ? JSON.parse(profile.profile_json) : null;
  const credits = user.credits ?? 0;

  return (
    <main className="pb-[60px]">
      <section className="bg-ink text-bone border-b-3 border-ink py-10">
        <div className="wrap">
          <h1 className="text-h2">Your stash</h1>
          <p className="text-[14.5px] opacity-90 mt-1.5">{user.email}</p>
          {/* How this account gets in. Worth stating plainly: someone who
              signed up with Google has no password, and finding that out at
              the sign-in screen months later - against an error that
              deliberately will not explain itself - is a bad afternoon. */}
        
        </div>
      </section>

      <div className="wrap pt-[30px]">
        {/* Status row. Only the account's state is coloured — four accented
            tiles would rank nothing, and this is a working surface rather
            than a landing page. */}
        <div className="grid gap-4 grid-cols-2 max-[620px]:grid-cols-1 mb-2">
          <div className={`${STAT} ${credits ? "bg-jade" : "bg-sun"}`}>
            <b className={STAT_N}>{credits}</b>
            <span className={STAT_L}>
              {credits === 1 ? "Credit left" : "Credits left"}
            </span>
          </div>
          <div className={`${STAT} bg-paper`}>
            <b className={STAT_N}>{deliveries.length}</b>
            <span className={STAT_L}>Stash so far</span>
          </div>
        </div>

        {/* resume */}
        <div className="sechead bg-paper">
          <h2 className="text-xl">Your resume</h2>
        </div>

        {profile ? (
          <div className="card mb-2.5">
            {/* The escape hatch sits on its own row rather than beside the
                heading, where it crowds it. */}
            <div className="flex items-start justify-between gap-4 flex-wrap mb-4">
              <div>
                <b className="text-base">{profile.resume_name}</b>
                <p className="text-[12.5px] opacity-60 mt-[3px] font-semibold">
                  Read {new Date(profile.updated_at).toLocaleDateString("en-GB", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  })}
                </p>
              </div>
              <Link href="/upload" className="btn btn-paper btn-sm flex-none">
                Replace
              </Link>
            </div>

            {/* The attributes that actually decide what gets scored in, laid
                out rather than crammed into one dot-separated line. Skills are
                the long tail and are folded away; see below. */}
            <div className={FACTS}>
              <ExperienceCounter
                initialYears={parsed.years_experience ?? null}
                initialLevel={parsed.level}
                cell={FACT}
                label={FACT_K}
                value={FACT_V}
              />
              <div className={FACT}>
                <span className={FACT_K}>Based in</span>
                <b className={`${FACT_V} capitalize`}>{parsed.home_country}</b>
              </div>
              <div className={FACT}>
                <span className={FACT_K}>Work setup</span>
                {/* Resumes rarely say this, so it is the user's to pick. */}
                <div className={FACT_V}>
                  <WorkSetupSelect initial={workSetupOf(parsed)} />
                </div>
              </div>
              <div className={FACT}>
                <span className={FACT_K}>Skills</span>
                <b className={FACT_V}>
                  {Object.keys(parsed.strong_skills || {}).length}
                </b>
              </div>
              <div className={FACT}>
                <span className={FACT_K}>Sponsorship</span>
                <b className={FACT_V}>
                  {(parsed.sponsorship_targets || []).length
                    ? (parsed.sponsorship_targets || []).join(", ").toUpperCase()
                    : "Not sought"}
                </b>
              </div>
            </div>

            {/* Closed by default: 28 tags is a wall, and the count above is
                the part that matters day to day. Open, each one is a switch —
                see SkillToggles. */}
            <details className="group">
              <summary
                className="text-[12.5px] font-extrabold cursor-pointer list-none
                           opacity-70 hover:opacity-100
                           after:content-['▾'] after:ml-1
                           group-open:after:content-['▴']"
              >
                Show the {Object.keys(parsed.strong_skills || {}).length} skills
                read from this resume
              </summary>
              <SkillToggles
                skills={Object.keys(parsed.strong_skills || {}).sort()}
                disabled={parsed.disabled_skills || []}
              />
            </details>
          </div>
        ) : (
          /* Sun, not the button colour: a missing resume is a blocker, and
             the button inside this card is the actual action. */
          <div className="card bg-sun mb-2.5">
            <b className="text-base">No resume yet</b>
            <p className="text-sm mt-1.5 mb-3.5 font-semibold">
              There&rsquo;s nothing to score jobs against until you upload one.
            </p>
            <Link href="/upload" className="btn btn-paper btn-sm">
              Upload a resume
            </Link>
          </div>
        )}

        {/* The section head that used to sit here is gone, and the button
            inside DigestPanel labels itself, so this only has to restore the
            gap the head was providing. */}
        <div className="mt-[30px]">
          <DigestPanel hasProfile={!!profile} credits={credits} openRun={openRun ?? null} />
        </div>

        {/* credits — sun only when the balance is empty, because that is when
            buying is the next thing to do. */}
        <div id="buy" className={`sechead scroll-mt-4 ${credits ? "bg-paper" : "bg-sun"}`}>
          <h2 className="text-xl">Buy credits</h2>
        </div>
        <BuyCredits />

        {/* history */}
        {deliveries.length > 0 && (
          <>
            <div className="sechead bg-paper">
              <h2 className="text-xl">Stash</h2>
            </div>
            {deliveries.map((d) => {
              /* What this run was scored with. Read off the digest itself, so
                 changing the resume or the work setup later does not rewrite
                 the history of runs made before it. Rows written before those
                 fields existed fall back to the profile as it stands. */
              const st = settingsOf(d.summary_json);
              const setup = (st.setup ??
                (parsed ? workSetupOf(parsed) : null)) as WorkSetup | null;
              const years = st.years ?? parsed?.years_experience ?? null;
              const meta = [
                d.day,
                setup ? WORK_SETUP_LABEL[setup] : null,
                years != null ? `${years} yr${years === 1 ? "" : "s"}` : null,
                `${d.matches} match${d.matches === 1 ? "" : "es"}`,
              ].filter(Boolean);
              return (
              <div
                className="border-3 border-ink bg-paper text-ink shadow-brut-sm px-[18px] py-4 mb-3"
                key={d.id}
              >
                {/* The title area: which resume was run, and under what
                    settings. It carries what used to sit to the left of the
                    boxes - and the trash, which below 720px was otherwise
                    left stranded on a line of its own - so the boxes get the
                    whole width underneath at every size. */}
                <div className="flex items-start gap-3 pb-2.5 mb-3 border-b-3 border-ink">
                  <div className="min-w-0 flex-1">
                    <h3 className="text-[15.5px] leading-tight break-words">
                      {st.name || profile?.resume_name || "Resume"}
                    </h3>
                    <p className="text-[12.5px] font-semibold opacity-70 mt-[3px]">
                      {meta.join(" · ")}
                    </p>
                  </div>
                  <DeleteDigest id={d.id} day={d.day} />
                </div>

                <div className="flex flex-wrap gap-1.5 items-center">
                  {/* ?v= is a cache-buster, not a parameter the route reads.
                      A 410 from before the download fix is still sitting in
                      browsers; 410 is heuristically cacheable and the route's
                      no-store cannot evict an entry stored without it. A URL
                      that was never poisoned is the only thing that gets past
                      it. */}
                  {/* One box per section, widest first. flex-basis is the job
                      count, so a run with 50 strong matches has a visibly
                      fatter green box than one with 12 - the ranking is the
                      display, without a word of copy saying so. min-w keeps a
                      small section from collapsing under its own label, which
                      does mean a very lopsided run overstates its smallest
                      box; the title carries the true count. */}
                  {(() => {
                    const parts = partsOf(d.summary_json);
                    const v = encodeURIComponent(d.created_at);
                    // A digest rendered before the boxes existed has no parts
                    // and no per-section files to offer. It keeps the pair it
                    // was delivered with: dropping PDF here would have taken
                    // the button away from every digest already in the stash.
                    if (!parts.length)
                      return (
                        <div className="flex gap-[7px] shrink-0">
                          <a
                            className="btn btn-paper btn-sm"
                            href={`/api/download/${d.id}?format=html&v=${v}`}
                            target="_blank"
                            rel="noreferrer"
                          >
                            View
                          </a>
                          {d.pdf_path && (
                            <a
                              className="btn btn-ink btn-sm"
                              href={`/api/download/${d.id}?v=${v}`}
                            >
                              PDF
                            </a>
                          )}
                        </div>
                      );
                    return (
                      <div className="flex gap-1.5 flex-1 min-w-0">
                        {parts.map((p) => (
                          <div
                            key={p.key}
                            title={`${p.label} · ${p.count} job${p.count === 1 ? "" : "s"}`}
                            /* The grow factor is a custom property rather
                               than an inline `flex`, so the media query below
                               can drop it. Inline styles beat any class, and
                               on a phone 23/58/20 squeezes Strong Matches to
                               about 75px - narrower than its own label. */
                            style={
                              { "--g": p.count, background: p.colour } as React.CSSProperties
                            }
                            className="[flex:var(--g)_1_0] max-[720px]:[flex:1_1_0] min-w-[104px] max-[720px]:min-w-0 border-3 border-ink shadow-brut-sm flex items-stretch"
                          >
                            <a
                              className="flex-1 min-w-0 px-2.5 py-2 text-[12px] font-extrabold leading-tight text-ink no-underline"
                              href={`/api/download/${d.id}?format=html&part=${p.key}&v=${v}`}
                              target="_blank"
                              rel="noreferrer"
                            >
                              {p.label}
                            </a>
                            {/* Two targets in one box: the label reads it in
                                the browser, the glyph saves the PDF. One click
                                for either, instead of making everyone open the
                                page to reach a download. */}
                            {p.pdf !== false && (
                              <a
                                className="shrink-0 px-2 flex items-center text-ink no-underline"
                                href={`/api/download/${d.id}?part=${p.key}&v=${v}`}
                                aria-label={`Download ${p.label} as PDF`}
                              >
                                <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
                                     stroke="currentColor" strokeWidth="2.5"
                                     strokeLinecap="round" strokeLinejoin="round"
                                     aria-hidden="true">
                                  <path d="M12 3v12m0 0 4-4m-4 4-4-4" />
                                  <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
                                </svg>
                              </a>
                            )}
                          </div>
                        ))}
                      </div>
                    );
                  })()}
                </div>
              </div>
              );
            })}
          </>
        )}
      </div>
    </main>
  );
}
