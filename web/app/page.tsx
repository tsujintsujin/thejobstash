import Link from "next/link";
import { poolPages, poolStats } from "@/lib/db";
import { currentUser } from "@/lib/session";
import { googleConfigured } from "@/lib/google";
import { FREE_CREDITS, PACKS, TEST_PRICE_PHP, chargePhp } from "@/lib/packs";
import { ROLE_ORDER, copyFor } from "@/lib/roles";
import {
  JsonLd,
  SITE_DESCRIPTION,
  SITE_NAME,
  SITE_TAGLINE,
  SITE_URL,
  pageMeta,
} from "@/lib/site";
import { CONTACT_EMAIL, OPERATOR } from "./legal/shell";
import AuthModal from "./AuthModal";
import UploadModal from "./UploadModal";

export const dynamic = "force-dynamic";

export const metadata = pageMeta({
  title: `${SITE_NAME} — ${SITE_TAGLINE.toLowerCase()}`,
  absolute: true,
  path: "/",
  description: SITE_DESCRIPTION,
});

/** Organization, WebSite, the product with its real prices, and the FAQ.
 *  Prices come from packs.ts and the answers from FAQ, so none can drift. */
function structuredData(faq: string[][]) {
  const org = `${SITE_URL}/#organization`;
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Organization",
        "@id": org,
        name: SITE_NAME,
        legalName: OPERATOR,
        url: SITE_URL,
        logo: `${SITE_URL}/icon.png`,
        email: CONTACT_EMAIL,
        areaServed: { "@type": "Country", name: "Philippines" },
      },
      {
        "@type": "WebSite",
        "@id": `${SITE_URL}/#website`,
        name: SITE_NAME,
        url: SITE_URL,
        inLanguage: "en-PH",
        publisher: { "@id": org },
      },
      {
        "@type": "WebApplication",
        name: SITE_NAME,
        url: SITE_URL,
        applicationCategory: "BusinessApplication",
        operatingSystem: "Any (web browser)",
        description: SITE_DESCRIPTION,
        provider: { "@id": org },
        offers: [
          {
            "@type": "Offer",
            name: `${FREE_CREDITS} free run`,
            price: 0,
            priceCurrency: "PHP",
          },
          ...PACKS.map((p) => ({
            "@type": "Offer",
            name: `${p.credits} credits`,
            price: p.php,
            priceCurrency: "PHP",
          })),
        ],
      },
      {
        "@type": "FAQPage",
        mainEntity: faq.map(([q, a]) => ({
          "@type": "Question",
          name: q,
          acceptedAnswer: { "@type": "Answer", text: a },
        })),
      },
    ],
  };
}

/* Layout patterns repeated across the page. Kept as constants rather than
   component classes because they are pure layout — no colour decision lives
   in here, so a band's accent stays visible at the element that wears it. */
const G4 =
  "grid gap-4 grid-cols-4 max-[900px]:grid-cols-2 max-[620px]:grid-cols-1";
const G3 =
  "grid gap-4 grid-cols-3 max-[900px]:grid-cols-2 max-[620px]:grid-cols-1";
const STAT = "border-3 border-ink shadow-brut text-ink px-5 py-[18px]";
const STAT_N =
  "block text-[38px] font-extrabold tracking-[-0.03em] leading-none";
// Full ink, no opacity: at 11px the faded label failed contrast on sun and
// coral (Lighthouse, 2026-09-17).
const STAT_L =
  "text-[11px] font-extrabold uppercase tracking-[0.09em]";
const SCORE =
  "border-2 border-ink bg-jade text-ink text-xs font-extrabold px-2.5 py-[3px] whitespace-nowrap";

const MARQUEE = [
  "FOR PEOPLE WHO HATE JOB BOARDS",
  "FOR CAREER SWITCHERS",
  "FOR THE OVER-QUALIFIED",
  "FOR THE UNDER-CONSIDERED",
  "FOR ANYONE TIRED OF SCROLLING",
  "FOR PEOPLE WHO WANT ONE GOOD LIST",
];

const STEPS = [
  {
    n: "01",
    bg: "bg-paper",
    h: "Upload once",
    p: "PDF or Word. We read the skills you actually shipped, the years you actually worked, and where you can legally work.",
  },
  {
    n: "02",
    bg: "bg-paper",
    h: "We sweep",
    p: "Thirteen job boards, swept every few hours, and a posting that closes is cleared out. One role posted on four boards shows up once.",
  },
  {
    n: "03",
    bg: "bg-paper",
    h: "We score",
    p: "Every posting against your resume. Skills, seniority, location, work authorisation, timezone.",
  },
  {
    // The payoff step is the inverted one. Four cards in four different
    // accents was a rainbow that ranked nothing; one dark card at the end
    // ranks the step that is actually the product.
    n: "04",
    bg: "bg-ink text-bone",
    h: "You get the list",
    p: "A short digest the moment your run finishes: your best matches, and what blocked the rest.",
  },
];

const FAQ = [
  [
    "How is this different from a job board?",
    "A job board shows you everything and makes you filter. We do the opposite: we throw away about 96% of what we scrape and show you what's left. The discarded pile is the product — thousands of postings a day that are in the wrong country, need work authorisation you don't hold, want twice your years, or centre on tools you've never touched.",
  ],
  [
    "How do credits work?",
    // Pack sizes and prices from packs.ts: this answer is also the FAQPage
    // structured data, so a stale figure here would be served to Google too.
    `One credit is one run: we score every live posting in the pool against your resume and hand you the digest. The pool itself is refreshed from the boards every few hours, whether anyone runs or not. Every account starts with ${FREE_CREDITS} free. After that you buy a pack of ${PACKS.map((p) => `${p.credits} for ₱${p.php}`).join(", ")} through PayMongo. No subscription, nothing recurring, and credits don't expire.`,
  ],
  [
    "What does 'came close' mean?",
    "Roles that matched your actual work but were blocked by exactly one thing — the wrong country, a timezone window, a couple of years too many. We show them with the reason attached, because a quiet run where you can see what's in the way is more useful than a short list with no explanation.",
  ],
  [
    "Will I get the same jobs over and over?",
    "Only while they're still your best matches. Every run scores the whole pool against your resume from scratch, so a strong role that's still listed stays in your digest, and new postings take its place as soon as they score higher.",
  ],
  [
    "What if a run turns up nothing good?",
    "You get a shorter digest that says so plainly, with the near-misses and their reasons. It still uses the credit, because the scoring happened, but we'd rather hand you a short honest list than pad it with roles that don't fit. A run that fails outright gives the credit back.",
  ],
  [
    "Do I need to link any accounts?",
    "No. No bank, no LinkedIn, no OAuth scopes. A resume file and an email address.",
  ],
  [
    "Is my resume shared with employers?",
    "Never. It's used to score postings and nothing else. You can delete it from the dashboard, which removes the parsed profile with it.",
  ],
];

export default async function Home() {
  const [stats, roles] = await Promise.all([poolStats(), poolPages()]);
  const user = await currentUser();
  const googleReady = googleConfigured();
  const browse = ROLE_ORDER.map((s) => roles.find((r) => r.slug === s)).filter(
    (r): r is (typeof roles)[number] => !!r
  );

  return (
    <main>
      <JsonLd data={structuredData(FAQ)} />
      {/* hero — the identity band above the fold. Lime rather than the action
          colour on the eyebrow and the card shadow: the hero states the
          promise, and flare is held back for the thing you press. */}
      <section className="band bg-azure text-bone py-[72px] max-[560px]:py-[52px]">
        <div
          className="wrap grid grid-cols-[1.05fr_.95fr] gap-12 items-center
                     max-[1000px]:grid-cols-1 max-[1000px]:gap-[34px]"
        >
          <div>
            <span className="eyebrow bg-lime text-ink">
              The job list for people who hate job hunting
            </span>
            <h1 className="text-display mt-[26px] mb-[18px]">
              Stop scrolling.
              <br />
              Start applying.
            </h1>
            <p className="lede opacity-95 mb-[30px]">
              Upload your resume once. Each time you run it, we score
              thousands of live postings, remote and in the Philippines, from
              13 job boards against it and hand you the handful
              worth your time — plus the ones that came close, and exactly what
              blocked them. Closed postings are cleared out every few hours.
            </p>
            <div className="flex gap-3.5 flex-wrap">
              {/* Scoring costs one machine real work, so nothing runs a
                  resume without an account behind it. Signed out, this opens
                  the signup card in a dialog rather than navigating off the
                  page before anyone has read what the product does. */}
              {user ? (
                <UploadModal label="Upload resume" />
              ) : (
                <AuthModal
                  label="Upload a resume — free"
                  googleReady={googleReady}
                  pool={stats.pool}
                  sources={stats.sources}
                />
              )}
              <Link href="/how-it-works" className="btn btn-paper">
                See how it works
              </Link>
            </div>
            {/* No opacity: bone on azure is 4.98:1 at full strength and
                under 4.5 once faded, which failed at this size. */}
            <p className="text-[13px] mt-[18px]">
              Free account, and your first run is on us. No card, no
              subscription.
            </p>
          </div>

          {/* A real digest, shrunk. Shows the near-miss section on the landing
              page, because that is the part people have not seen before.

              The sample is a virtual assistant, not a developer, on purpose.
              The scrapers skew technical, so a page full of React roles reads
              as a developer tool and quietly tells every VA, bookkeeper and
              support rep that the product is not for them - when they are the
              2,110 postings the old pipeline threw away as "not a software
              job". The three blockers below are still the real vocabulary:
              seniority, geography, timezone.

              Dropped rather than stacked on phones: it is decorative, and
              stacked it would push the real call to action below the fold. */}
          <div className="max-[640px]:hidden">
            <div className="card shadow-brut-lime p-0">
              <div className="bg-ink text-bone px-4 py-3 flex justify-between items-baseline">
                <b className="text-sm">Your digest</b>
                <span className="text-[10px] tracking-[.1em] opacity-75">
                  THIS RUN
                </span>
              </div>
              <div className="p-3.5">
                <div className="tag bg-jade mb-2.5">Strong matches — 3</div>
                {[
                  ["Executive Virtual Assistant", "Remote · worldwide", 26],
                  ["E-commerce Support VA", "APAC · remote", 21],
                ].map(([t, m, s]) => (
                  <div
                    key={t as string}
                    className="border-2 border-ink px-[11px] py-[9px] mb-2
                               flex justify-between gap-2.5 items-center"
                  >
                    <div>
                      <b className="text-[13px] block">{t}</b>
                      <span className="text-[11px] opacity-70 font-semibold">
                        {m}
                      </span>
                    </div>
                    <span className={SCORE}>{s}</span>
                  </div>
                ))}

                {/* Sun, not the button colour. These are blockers, and the
                    previous palette painted them in the same coral as the
                    primary CTA — so "came close" and "press here" were the
                    same colour. */}
                <div className="tag bg-sun mt-3.5 mb-2.5">Came close — 8</div>
                {[
                  ["Customer Support Associate", "Onsite in Cebu"],
                  ["Real Estate Appointment Setter", "Asks for 5+ years"],
                  ["Social Media Assistant", "Limited to UTC-5"],
                ].map(([t, why]) => (
                  <div
                    key={t as string}
                    className="border-l-4 border-ink pl-[9px] py-[3px] mb-[7px]"
                  >
                    <b className="text-[12.5px] block">{t}</b>
                    <span className="text-[11px] opacity-75 font-semibold">
                      {why}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      <div className="bg-sun border-b-3 border-ink overflow-hidden whitespace-nowrap py-[11px]">
        <div className="marquee-inner">
          {[...MARQUEE, ...MARQUEE].map((m, i) => (
            <span
              key={i}
              className="text-xs font-extrabold uppercase tracking-[0.11em] px-[22px]"
            >
              {m} &nbsp;&bull;
            </span>
          ))}
        </div>
      </div>

      {/* live numbers */}
      <section className="band band-tight">
        <div className="wrap">
          <h2 className="text-h2 mb-2.5">Live right now</h2>
          <p className="lede mb-[26px]">
            These are real numbers from the pool this instance is scoring
            against — not a marketing figure.
          </p>
          {/* The one four-colour block on the page. These are four facts of
              equal weight, so none of them outranks another and the colour is
              rhythm rather than meaning. Every other accented group ranks. */}
          <div className={G4}>
            <div className={`${STAT} bg-sun`}>
              <b className={STAT_N}>{stats.pool.toLocaleString()}</b>
              <span className={STAT_L}>Live postings</span>
            </div>
            <div className={`${STAT} bg-coral`}>
              <b className={STAT_N}>{stats.fresh.toLocaleString()}</b>
              <span className={STAT_L}>Added in 3 days</span>
            </div>
            <div className={`${STAT} bg-jade`}>
              <b className={STAT_N}>{stats.sources}</b>
              <span className={STAT_L}>Boards swept</span>
            </div>
            {/* Was "~20 per digest", which stopped being true when the cap
                of 20 went (HANDOFF-DIGEST-BOXES.md). A figure under "not a
                marketing figure" has to be one the code guarantees. */}
            <div className={`${STAT} bg-lime`}>
              <b className={STAT_N}>{FREE_CREDITS}</b>
              <span className={STAT_L}>Free run to start</span>
            </div>
          </div>
          {/* Browse — the home page's links into /jobs. Search engines reach
              the role pages through here; a page nothing links to barely ranks. */}
          {browse.length > 0 && (
            <div className="mt-9">
              <h2 className="text-h3 mb-3.5">Browse by kind of work</h2>
              <ul className="flex flex-wrap gap-2 list-none p-0">
                {browse.map((r) => (
                  <li key={r.slug}>
                    <Link
                      href={`/jobs/${r.slug}`}
                      className="tag no-underline hover:bg-sun"
                    >
                      {copyFor(r.slug, r.name).plural} ·{" "}
                      {r.total.toLocaleString()}
                    </Link>
                  </li>
                ))}
                <li>
                  <Link href="/jobs" className="tag bg-ink text-bone no-underline">
                    All roles →
                  </Link>
                </li>
              </ul>
            </div>
          )}
        </div>
      </section>

      {/* how */}
      <section id="how" className="band bg-grape text-bone">
        <div className="wrap">
          <h2 className="text-h2 mb-2.5">
            Four steps. That&rsquo;s the whole system.
          </h2>
          <p className="lede mb-[30px]">
            No dashboards to maintain, no filters to tune, no daily check-in.
          </p>
          <div className={G4}>
            {STEPS.map((s) => (
              <div key={s.n} className={`card ${s.bg}`}>
                <span className="font-mono text-[13px] font-extrabold">
                  {s.n}
                </span>
                <h3 className="text-h3 mt-2.5 mb-2">{s.h}</h3>
                <p className="text-sm leading-normal">{s.p}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* the 96% */}
      <section className="band">
        <div className="wrap">
          <div
            className="grid grid-cols-2 gap-10 items-center
                       max-[860px]:grid-cols-1 max-[860px]:gap-[26px]"
          >
            <div>
              <span className="eyebrow">The part nobody else does</span>
              <h2 className="text-h2 mt-5 mb-4">
                We throw away 96% of what we find.
              </h2>
              <p className="lede mb-3.5">
                Most job tools optimise for how much they can show you. That
                number is easy to grow and useless to act on — nobody applies to
                a hundred jobs a day, or reads them.
              </p>
              <p className="lede">
                So we do the opposite. Wrong country, work authorisation you
                don&rsquo;t hold, a timezone you can&rsquo;t cover, twice your
                years, built on a tool you&rsquo;ve never shipped — all gone
                before the email is written. What survives is short on purpose.
              </p>
            </div>
            {/* A descent, not a rotation: the noisy input is sun, what
                survives is lime, and the absolute at the bottom is ink. */}
            <div className="grid gap-3">
              <div className="card bg-sun">
                <b className="text-[30px] tracking-[-0.03em]">~1,000</b>
                <p className="text-sm font-bold mt-1">
                  new postings a day across the boards
                </p>
              </div>
              <div className="card bg-lime">
                <b className="text-[30px] tracking-[-0.03em]">~20</b>
                <p className="text-sm font-bold mt-1">
                  survive scoring against one resume
                </p>
              </div>
              <div className="card bg-ink text-bone">
                <b className="text-[30px] tracking-[-0.03em]">~10</b>
                <p className="text-sm font-bold mt-1">
                  came close, with the reason attached
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* pricing */}
      <section id="pricing" className="band bg-sun">
        <div className="wrap">
          <span className="eyebrow">Credits</span>
          <h2 className="text-h2 mt-5 mb-2.5">Pay per run, not a subscription.</h2>
          <p className="lede mb-[30px]">
            One credit is one run of your resume: every live posting scored,
            your digest handed over. Every account starts with{" "}
            {FREE_CREDITS} free. Nothing recurs, and credits don&rsquo;t expire.
          </p>
          <div className={G3}>
            {PACKS.map((p, i) => (
              // The middle pack is the recommended one, so it is the only one
              // wearing an accent — jade, because it is a recommendation
              // rather than a warning.
              <div
                key={p.id}
                className={`card flex flex-col p-[22px] ${i === 1 ? "bg-jade" : "bg-paper"}`}
              >
                <span className="tag self-start">{p.credits} credits</span>
                <div className="text-[34px] font-extrabold tracking-[-0.03em] mt-2 mb-1">
                  ₱{chargePhp(p)}{" "}
                  {TEST_PRICE_PHP !== null && (
                    <s className="text-[17px] opacity-45 font-bold">₱{p.php}</s>
                  )}
                </div>
                <ul className="list-none mt-3.5 mb-5">
                  {[
                    `${p.credits} runs of your resume`,
                    `About ₱${Math.round(p.php / p.credits)} a run`,
                    "Scored against a pool refreshed every few hours",
                    "Pay with QR Ph: GCash, Maya or your bank app",
                  ].map((l) => (
                    <li
                      key={l}
                      className="text-[13.5px] font-semibold py-[5px]
                                 border-b border-ink-line last:border-b-0"
                    >
                      {l}
                    </li>
                  ))}
                </ul>
                <Link
                  href={user ? "/dashboard#buy" : "/signup"}
                  className="btn btn-ink mt-auto text-center"
                >
                  {user ? "Buy credits" : "Start with 1 free run"}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* faq — coral, not flare. It is the longest reading on the page, so it
          gets the warm ground rather than the loud one; the two reds are far
          enough apart that this never reads as a band-sized button. */}
      <section id="faq" className="band bg-coral">
        <div className="wrap">
          <h2 className="text-h2 mb-2">Reasonable questions</h2>
          <p className="lede mb-7">
            Including the ones where the honest answer isn&rsquo;t flattering.
          </p>
          <div className="max-w-[780px]">
            {FAQ.map(([q, a]) => (
              <details
                className="group border-3 border-ink bg-paper shadow-brut-sm mb-[11px]"
                key={q}
              >
                <summary
                  className="px-[18px] py-[15px] font-extrabold text-[15px]
                             cursor-pointer list-none flex justify-between gap-3
                             after:content-['+'] after:text-xl after:leading-none
                             group-open:after:content-['−']"
                >
                  {q}
                </summary>
                <p className="px-[18px] pb-4 text-sm leading-[1.55]">{a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* closer — azure, bookending the hero. The page opens and closes on
          the same blue, and flare stays on the button inside it rather than
          swallowing the whole block. */}
      <section className="band bg-azure text-bone text-center">
        <div className="narrow">
          <h2 className="text-h2 mb-4">One resume. One credit. One good list.</h2>
          <p className="lede mx-auto mb-7">
            Takes about thirty seconds to set up, and your first run is
            on us.
          </p>
          <div className="flex justify-center">
            {user ? (
              <UploadModal label="Upload resume" />
            ) : (
              <AuthModal
                label="Scan my resume — free"
                googleReady={googleReady}
                pool={stats.pool}
                sources={stats.sources}
              />
            )}
          </div>
        </div>
      </section>
    </main>
  );
}
