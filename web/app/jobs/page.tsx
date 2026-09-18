import Link from "next/link";
import { poolPages, poolStats } from "@/lib/db";
import { ROLE_ORDER, copyFor } from "@/lib/roles";
import { JsonLd, SITE_URL, pageMeta } from "@/lib/site";

export const dynamic = "force-dynamic";

export const metadata = pageMeta({
  title: "Job openings in the Philippines by role — online, WFH and onsite",
  path: "/jobs",
  description:
    "Live job openings in the Philippines, grouped by the kind of work: " +
    "online and work-from-home, part-time, entry-level, non-voice, virtual " +
    "assistant, customer service, accounting and more. Checked every few hours.",
});

const n = (x: number) => x.toLocaleString("en-US");

export default async function JobsIndex() {
  const [pages, stats] = await Promise.all([poolPages(), poolStats()]);
  const ordered = ROLE_ORDER.map((s) => pages.find((p) => p.slug === s)).filter(
    (p): p is (typeof pages)[number] => !!p
  );

  return (
    <main>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "BreadcrumbList",
          itemListElement: [
            { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
            { "@type": "ListItem", position: 2, name: "Jobs", item: `${SITE_URL}/jobs` },
          ],
        }}
      />
      <section className="band bg-azure text-bone py-[64px] max-[560px]:py-[46px]">
        <div className="wrap">
          <span className="eyebrow bg-lime text-ink">Browse the pool</span>
          <h1 className="text-h2 mt-[22px] mb-4 max-w-[20ch]">
            Jobs in the Philippines, by kind of work
          </h1>
          <p className="lede mb-7">
            {n(stats.pool)} live postings, remote and onsite, with closed ones cleared out every few hours.
            Pick a kind of work to see what is open, or upload your resume and
            let a run find the ones that fit you.
          </p>
          <Link href="/signup" className="btn">
            Match my resume — free
          </Link>
        </div>
      </section>

      <section className="band">
        <div className="wrap">
          {ordered.length === 0 ? (
            <p className="lede">The role pages are being refreshed. Check back shortly.</p>
          ) : (
            <ul className="grid gap-4 grid-cols-3 max-[900px]:grid-cols-2 max-[560px]:grid-cols-1 list-none p-0">
              {ordered.map((p) => (
                <li key={p.slug}>
                  <Link
                    href={`/jobs/${p.slug}`}
                    className="card bg-paper no-underline flex flex-col h-full
                               hover:bg-sun transition-colors"
                  >
                    <h2 className="text-h3 mb-2">{copyFor(p.slug, p.name).plural}</h2>
                    <span className="text-[14px] font-semibold">
                      <b className="text-[22px] font-extrabold tracking-[-0.02em]">
                        {n(p.total)}
                      </b>{" "}
                      live · {n(p.fresh)} this week
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </main>
  );
}
