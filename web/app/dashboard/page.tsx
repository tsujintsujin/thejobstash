import Link from "next/link";
import { redirect } from "next/navigation";
import { currentUser } from "@/lib/session";
import {
  activeEntitlement,
  deliveriesFor,
  profileFor,
  poolStats,
  todayIso,
} from "@/lib/db";
import DigestPanel from "./DigestPanel";
import PlanPicker from "./PlanPicker";
import { G4, SECHEAD_NOTE, STAT, STAT_L, STAT_N } from "../ui";

export const dynamic = "force-dynamic";

const PLAN_NAME: Record<string, string> = {
  one_time: "One sweep",
  three_day: "Three days",
  seven_day: "Seven days",
};

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
const FACT_NOTE =
  "block not-italic text-[11.5px] font-semibold opacity-65 mt-[3px] leading-[1.35]";

function daysLeft(endsOn: string) {
  const end = new Date(endsOn + "T23:59:59Z").getTime();
  return Math.max(0, Math.ceil((end - Date.now()) / 86400000));
}

export default async function Dashboard() {
  const user = await currentUser();
  if (!user) redirect("/signup?mode=signin");

  // Four independent reads, so they go together rather than one after the
  // other - each is a network round trip to D1 now, not a local file read.
  const [profile, ent, deliveries, stats] = await Promise.all([
    profileFor(user.id),
    activeEntitlement(user.id),
    deliveriesFor(user.id),
    poolStats(),
  ]);
  const parsed = profile ? JSON.parse(profile.profile_json) : null;
  const deliveredToday = deliveries.some((d) => d.day === todayIso());

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
          <p className="text-[12.5px] opacity-70 mt-1 font-semibold">
            {user.google_sub && user.password_hash
              ? "Sign in with Google or your password"
              : user.google_sub
                ? "Signed in with Google — this account has no password"
                : "Signed in with an email and password"}
          </p>
        </div>
      </section>

      <div className="wrap pt-[30px]">
        {/* Status row. Only the account's state is coloured — four accented
            tiles would rank nothing, and this is a working surface rather
            than a landing page. */}
        <div className={`${G4} mb-2`}>
          <div className={`${STAT} ${ent ? "bg-jade" : "bg-sun"}`}>
            <b className={STAT_N}>{ent ? daysLeft(ent.ends_on) : 0}</b>
            <span className={STAT_L}>{ent ? "Days left" : "No active plan"}</span>
          </div>
          <div className={`${STAT} bg-paper`}>
            <b className={STAT_N}>{ent ? PLAN_NAME[ent.plan] ?? ent.plan : "—"}</b>
            <span className={STAT_L}>Current plan</span>
          </div>
          <div className={`${STAT} bg-paper`}>
            <b className={STAT_N}>{deliveries.length}</b>
            <span className={STAT_L}>Digests so far</span>
          </div>
          <div className={`${STAT} bg-paper`}>
            <b className={STAT_N}>{stats.pool.toLocaleString()}</b>
            <span className={STAT_L}>Jobs in the pool</span>
          </div>
        </div>

        {/* resume */}
        <div className="sechead bg-paper">
          <h2 className="text-xl">Your resume</h2>
          <em className={SECHEAD_NOTE}>What everything gets scored against</em>
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
                out rather than crammed into one dot-separated line. Each cell
                is label, value, and one line saying what that value does — a
                number with no consequence attached is trivia. Skills are the
                long tail and are folded away; see below. */}
            <div className={FACTS}>
              <div className={FACT}>
                <span className={FACT_K}>Experience</span>
                <b className={FACT_V}>{parsed.years_experience} yrs</b>
                <em className={FACT_NOTE}>relevant to this field</em>
              </div>
              <div className={FACT}>
                <span className={FACT_K}>Seniority</span>
                <b className={`${FACT_V} capitalize`}>{parsed.level}</b>
                <em className={FACT_NOTE}>roles above this are a stretch</em>
              </div>
              <div className={FACT}>
                <span className={FACT_K}>Based in</span>
                <b className={`${FACT_V} capitalize`}>{parsed.home_country}</b>
                <em className={FACT_NOTE}>
                  {(parsed.authorized_in || []).length
                    ? `authorised to work in ${(parsed.authorized_in || [])
                        .join(", ")
                        .toUpperCase()}`
                    : "no work authorisation recorded"}
                </em>
              </div>
              <div className={FACT}>
                <span className={FACT_K}>Work setup</span>
                <b className={FACT_V}>
                  {parsed.remote_only ? "Remote only" : "Remote or onsite"}
                </b>
                <em className={FACT_NOTE}>
                  {parsed.wants_local_onsite
                    ? "onsite near you is fine"
                    : "onsite roles are filtered out"}
                </em>
              </div>
              <div className={FACT}>
                <span className={FACT_K}>Skills</span>
                <b className={FACT_V}>
                  {Object.keys(parsed.strong_skills || {}).length}
                </b>
                <em className={FACT_NOTE}>
                  a job needs {parsed.min_skill_hits} of them to qualify
                </em>
              </div>
              <div className={FACT}>
                <span className={FACT_K}>Sponsorship</span>
                <b className={FACT_V}>
                  {(parsed.sponsorship_targets || []).length
                    ? (parsed.sponsorship_targets || []).join(", ").toUpperCase()
                    : "Not sought"}
                </b>
                <em className={FACT_NOTE}>
                  {(parsed.sponsorship_targets || []).length
                    ? "visa-sponsoring roles are kept"
                    : "roles requiring relocation are dropped"}
                </em>
              </div>
            </div>

            {/* Closed by default: 28 tags is a wall, and the count above is
                the part that matters day to day. */}
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
              <div className="flex gap-1.5 flex-wrap mt-3">
                {Object.keys(parsed.strong_skills || {})
                  .sort()
                  .map((s) => (
                    <span key={s} className="tag">
                      {s}
                    </span>
                  ))}
              </div>
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

        {/* plan */}
        {!ent && (
          <>
            <div className="sechead bg-sun">
              <h2 className="text-xl">Start a plan</h2>
              <em className={SECHEAD_NOTE}>Free while payments are switched off</em>
            </div>
            <PlanPicker />
          </>
        )}

        {/* digest — the main event, so it takes the dark head. */}
        <div className="sechead bg-ink text-bone">
          <h2 className="text-xl">Today&rsquo;s matches</h2>
          <em className={SECHEAD_NOTE}>
            {deliveredToday
              ? "Already delivered today — this shows what's left in the pool"
              : "Scored live against your resume"}
          </em>
        </div>

        <DigestPanel
          hasProfile={!!profile}
          hasPlan={!!ent}
          deliveredToday={deliveredToday}
        />

        {/* history */}
        {deliveries.length > 0 && (
          <>
            <div className="sechead bg-paper">
              <h2 className="text-xl">Past digests</h2>
              <em className={SECHEAD_NOTE}>Every one is still downloadable</em>
            </div>
            {deliveries.map((d) => (
              <div
                className="border-3 border-ink bg-paper text-ink shadow-brut-sm px-[18px] py-4 mb-3"
                key={d.id}
              >
                <div className="flex justify-between gap-3.5 items-start">
                  <div>
                    <h3 className="text-[17px]">{d.day}</h3>
                    <div className="text-[13.5px] font-semibold mt-1.5">
                      <b className="font-extrabold">{d.matches}</b> matches ·{" "}
                      <b className="font-extrabold">{d.near_misses}</b> came close
                    </div>
                    <div className="text-xs opacity-70 mt-1 font-semibold">
                      email: {d.email_status}
                      {d.email_status === "outbox" && " (written to outbox/)"}
                    </div>
                  </div>
                  <div className="flex gap-[7px] flex-wrap">
                    <a
                      className="btn btn-paper btn-sm"
                      href={`/api/download/${d.id}?format=html`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      View
                    </a>
                    {d.pdf_path && (
                      <a className="btn btn-sm" href={`/api/download/${d.id}`}>
                        PDF
                      </a>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </>
        )}
      </div>
    </main>
  );
}
