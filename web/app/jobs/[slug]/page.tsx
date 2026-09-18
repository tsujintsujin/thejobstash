import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { poolPage, poolPages } from "@/lib/db";
import { ROLE_ORDER, copyFor } from "@/lib/roles";
import { JsonLd, SITE_URL, pageMeta } from "@/lib/site";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }> };

const STAT = "border-3 border-ink shadow-brut text-ink px-5 py-[18px]";
const STAT_N = "block text-[34px] font-extrabold tracking-[-0.03em] leading-none";
const STAT_L = "text-[11px] font-extrabold uppercase tracking-[0.09em]";

const n = (x: number) => x.toLocaleString("en-US");
const day = (iso: string) =>
  iso
    ? new Date(iso.slice(0, 10) + "T00:00:00Z").toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        timeZone: "UTC",
      })
    : "";

function heading(plural: string) {
  return `${plural} jobs in the Philippines`;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const page = await poolPage(slug);
  if (!page) return { title: "Not found", robots: { index: false } };
  const c = copyFor(slug, page.name);
  return pageMeta({
    title: heading(c.plural),
    path: `/jobs/${slug}`,
    description:
      `${n(page.total)} live ${c.plural.toLowerCase()} postings open to people ` +
      `in the Philippines, ${n(page.fresh)} posted this week. ` +
      `See which ones fit your resume, and what blocks the rest.`,
  });
}

export default async function RolePage({ params }: Props) {
  const { slug } = await params;
  const [page, all] = await Promise.all([poolPage(slug), poolPages()]);
  if (!page) notFound();
  const c = copyFor(slug, page.name);
  const h1 = heading(c.plural);
  const related = ROLE_ORDER.filter(
    (s) => s !== slug && all.some((p) => p.slug === s)
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
            { "@type": "ListItem", position: 3, name: h1, item: `${SITE_URL}/jobs/${slug}` },
          ],
        }}
      />

      <section className="band bg-azure text-bone py-[64px] max-[560px]:py-[46px]">
        <div className="wrap">
          <nav aria-label="Breadcrumb" className="text-[13px] font-bold mb-5">
            <Link href="/" className="underline">Home</Link>
            <span className="mx-2" aria-hidden>/</span>
            <Link href="/jobs" className="underline">Jobs</Link>
          </nav>
          <h1 className="text-h2 mb-4 max-w-[22ch]">{h1}</h1>
          <p className="lede mb-7">{c.intro}</p>
          <div className="flex gap-3.5 flex-wrap">
            <Link href="/signup" className="btn">
              See which ones fit my resume — free
            </Link>
            <Link href="/how-it-works" className="btn btn-paper">
              How matching works
            </Link>
          </div>
        </div>
      </section>

      <section className="band band-tight">
        <div className="wrap">
          <h2 className="text-h3 mb-4">Right now, in the pool</h2>
          <div className="grid gap-4 grid-cols-4 max-[900px]:grid-cols-2">
            <div className={`${STAT} bg-lime`}>
              <b className={STAT_N}>{n(page.total)}</b>
              <span className={STAT_L}>Live postings</span>
            </div>
            <div className={`${STAT} bg-sun`}>
              <b className={STAT_N}>{n(page.fresh)}</b>
              <span className={STAT_L}>Posted this week</span>
            </div>
            <div className={`${STAT} bg-jade`}>
              <b className={STAT_N}>{n(page.remote)}</b>
              <span className={STAT_L}>Remote or WFH</span>
            </div>
            <div className={`${STAT} bg-paper`}>
              <b className={STAT_N}>{n(page.with_pay)}</b>
              <span className={STAT_L}>State the pay</span>
            </div>
          </div>
          <p className="text-[13px] font-semibold mt-4">
            Counted from postings located in the Philippines or open to remote
            applicants. Updated {day(page.updated_at)}; closed postings are
            cleared out every few hours.
          </p>
        </div>
      </section>

      {page.examples.length > 0 && (
        <section className="band bg-paper border-y-3 border-ink">
          <div className="wrap">
            <h2 className="text-h2 mb-2.5">A few of them</h2>
            <p className="lede mb-7">
              A sample of recent postings, pay first where it is stated. Your
              run scores all {n(page.total)} against your resume and returns
              the ones that fit, with links to apply.
            </p>
            <ul className="grid gap-3 grid-cols-2 max-[760px]:grid-cols-1 list-none p-0">
              {page.examples.map((e, i) => (
                <li key={i} className="border-3 border-ink bg-bone px-4 py-3.5">
                  <b className="block text-[15px] leading-snug">{e.title}</b>
                  <span className="block text-[13px] font-semibold mt-1">
                    {[e.company, e.location].filter(Boolean).join(" · ")}
                  </span>
                  <span className="flex flex-wrap gap-2 items-center mt-2.5">
                    {e.salary && (
                      <span className="tag bg-jade normal-case tracking-normal">
                        {e.salary}
                      </span>
                    )}
                    <span className="text-[12px] font-bold">
                      {e.posted && day(e.posted)}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}

      {(c.asks.length > 0 || c.blockers.length > 0) && (
        <section className="band">
          <div className="wrap grid gap-5 grid-cols-2 max-[860px]:grid-cols-1">
            <div className="card bg-paper">
              <h2 className="text-h3 mb-3">What employers ask for</h2>
              <ul className="grid gap-2 list-none p-0">
                {c.asks.map((a) => (
                  <li key={a} className="border-l-3 border-ink pl-3 text-[15px] leading-[1.5]">
                    {a}
                  </li>
                ))}
              </ul>
            </div>
            <div className="card bg-sun">
              <h2 className="text-h3 mb-3">What gets applications filtered out</h2>
              <ul className="grid gap-2 list-none p-0">
                {c.blockers.map((b) => (
                  <li key={b} className="border-l-3 border-ink pl-3 text-[15px] leading-[1.5]">
                    {b}
                  </li>
                ))}
              </ul>
              <p className="text-[13px] font-semibold mt-4">
                These are the blockers a run checks for. Postings that miss by
                one of them come back as near-misses, with the reason attached.
              </p>
            </div>
          </div>
        </section>
      )}

      <section className="band bg-azure text-bone text-center">
        <div className="narrow">
          <h2 className="text-h2 mb-4">Skip the scrolling.</h2>
          <p className="lede mx-auto mb-7">
            Upload your resume once and get the {c.plural.toLowerCase()} roles
            that actually fit it. Your first run is free.
          </p>
          <div className="flex justify-center">
            <Link href="/signup" className="btn">
              Upload a resume — free
            </Link>
          </div>
        </div>
      </section>

      {related.length > 0 && (
        <section className="band band-tight">
          <div className="wrap">
            <h2 className="text-h3 mb-4">Other kinds of work</h2>
            <ul className="flex flex-wrap gap-2 list-none p-0">
              {related.map((s) => {
                const p = all.find((x) => x.slug === s)!;
                return (
                  <li key={s}>
                    <Link href={`/jobs/${s}`} className="tag no-underline hover:bg-sun">
                      {copyFor(s, p.name).plural} · {n(p.total)}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        </section>
      )}
    </main>
  );
}
