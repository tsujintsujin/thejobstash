import Link from "next/link";
import { P, Rows } from "@/app/legal/shell";
import { poolStats } from "@/lib/db";
import { FREE_CREDITS, PACKS } from "@/lib/packs";
import { BOARD_NAMES } from "@/lib/roles";
import { JsonLd, SITE_URL, pageMeta } from "@/lib/site";

export const dynamic = "force-dynamic";

export const metadata = pageMeta({
  title: "How it works: how jobs are matched to your resume",
  path: "/how-it-works",
  description:
    "How TheJobStash gathers postings from 13 job boards, clears out closed " +
    "ones every few hours, and scores each one against your resume on " +
    "skills, seniority, location, work authorisation and timezone.",
});

const n = (x: number) => x.toLocaleString("en-US");

function Step({
  n: num,
  title,
  children,
}: {
  n: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="grid grid-cols-[64px_1fr] gap-5 max-[560px]:grid-cols-1 max-[560px]:gap-2 mb-10">
      <span className="font-mono text-[28px] font-extrabold leading-none">{num}</span>
      <div>
        <h2 className="text-h3 mb-3">{title}</h2>
        {children}
      </div>
    </section>
  );
}

export default async function HowItWorks() {
  const stats = await poolStats();
  const boards = Object.values(BOARD_NAMES);

  return (
    <main>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "WebPage",
          name: "How TheJobStash matches jobs to your resume",
          url: `${SITE_URL}/how-it-works`,
          isPartOf: { "@type": "WebSite", name: "TheJobStash", url: SITE_URL },
        }}
      />
      <section className="band bg-grape text-bone py-[64px] max-[560px]:py-[46px]">
        <div className="wrap">
          <span className="eyebrow bg-lime text-ink">How it works</span>
          <h1 className="text-h2 mt-[22px] mb-4 max-w-[22ch]">
            How a resume becomes a short list of jobs worth applying to
          </h1>
          <p className="lede">
            Most job sites show you everything and leave the filtering to you.
            This does the filtering: it throws away the postings you cannot
            get, and tells you why the near-misses missed.
          </p>
        </div>
      </section>

      <section className="band">
        <div className="wrap">
          <div className="max-w-[860px]">
          <Step n="01" title="Postings are gathered from 13 job boards">
            <P>
              The pool is built from {boards.slice(0, 3).join(", ")} and ten
              international remote boards: {boards.slice(3).join(", ")}. Right
              now it holds {n(stats.pool)} live postings.
            </P>
            <P>
              The same role is often posted on several boards. Each is kept as
              its own posting, but a digest shows each company and title once,
              picking the copy that matches best.
            </P>
          </Step>

          <Step n="02" title="Closed postings are cleared out every few hours">
            <P>
              Every few hours each board is read again and compared with the
              pool. A posting a board has stopped listing is hidden from runs
              straight away, then opened to check whether it is really gone.
              It is deleted when:
            </P>
            <Rows
              rows={[
                ["The page is gone", "the board returns not found"],
                ["The board says it is closed", "for example “no longer accepting applications”"],
                ["It redirects away", "to a search page or the board's home page"],
                ["The page no longer describes the job", "most of the title is missing from it"],
              ]}
            />
            <P>
              A board that returns far fewer postings than usual (a failed
              scrape, not a quiet week) is read again, and if it is still
              short, skipped for that round. That way a scraping failure never
              wipes out real postings.
            </P>
          </Step>

          <Step n="03" title="Your resume is read once">
            <P>
              Upload a PDF or Word file. It is read for the skills you have
              actually used, your years of experience, your seniority, where
              you are, and where you can legally work. You choose remote,
              hybrid or onsite yourself on the dashboard, because a resume
              rarely says. Your resume is never shared with employers.
            </P>
          </Step>

          <Step n="04" title="Every posting is scored against it">
            <P>
              Each run scores the whole pool against your resume as it stands.
              A posting is checked for:
            </P>
            <Rows
              rows={[
                ["Skills", "how much of what the posting centres on you have actually done"],
                ["Seniority", "whether it asks for far more years than you have"],
                ["Geography and timezone", "whether it is open to someone where you are, in hours you can work"],
                ["Work authorisation", "whether it needs a visa or citizenship you do not hold"],
                ["Onsite", "whether it needs you in an office you cannot get to"],
              ]}
            />
          </Step>

          <Step n="05" title="You get a digest in three parts">
            <Rows
              rows={[
                ["Strong matches", "apply to these first"],
                ["Worth a look", "solid fits with a caveat or two"],
                ["Came close", "roles that matched your work but were blocked by one thing, with that thing named"],
              ]}
            />
            <P>
              The near-misses are the part most tools leave out. A short list
              with no explanation tells you nothing; a list of what keeps
              blocking you (a timezone, a missing tool, a few years) tells you
              what to fix or where to look instead.
            </P>
          </Step>

          <Step n="06" title="One run costs one credit">
            <P>
              Every account starts with {FREE_CREDITS} free run. After that,
              credits come in packs:{" "}
              {PACKS.map((p) => `${p.credits} for ₱${p.php}`).join(", ")}.
              No subscription, and credits do not expire. A run that fails
              gives its credit back automatically. See the{" "}
              <Link href="/refunds" className="underline font-bold">refund policy</Link>.
            </P>
          </Step>

          <div className="card bg-jade mt-4">
            <h2 className="text-h3 mb-2">See it on your own resume</h2>
            <p className="text-[15px] mb-4">
              Your first run is free, and it takes about thirty seconds to set up.
            </p>
            <div className="flex gap-3 flex-wrap">
              <Link href="/signup" className="btn">Upload a resume — free</Link>
              <Link href="/jobs" className="btn btn-paper">Browse jobs by role</Link>
            </div>
          </div>
          </div>
        </div>
      </section>
    </main>
  );
}
