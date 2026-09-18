import Link from "next/link";
import { CONTACT_EMAIL, OPERATOR, P } from "@/app/legal/shell";
import { JsonLd, SITE_URL, pageMeta } from "@/lib/site";

export const metadata = pageMeta({
  title: "About",
  path: "/about",
  description:
    "Who runs TheJobStash, why it exists, and how to reach us. A job matcher " +
    "built for people in the Philippines who are tired of scrolling job boards.",
});

export default function About() {
  return (
    <main>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "AboutPage",
          url: `${SITE_URL}/about`,
          mainEntity: { "@id": `${SITE_URL}/#organization` },
        }}
      />
      <section className="band bg-ink text-bone py-[64px] max-[560px]:py-[46px]">
        <div className="wrap">
          <span className="eyebrow bg-lime text-ink">About</span>
          <h1 className="text-h2 mt-[22px] mb-4 max-w-[20ch]">
            Built for people who hate job hunting
          </h1>
          <p className="lede opacity-90">
            TheJobStash is run by {OPERATOR}. It exists because job boards are
            built to show you as much as possible, and nobody needs more to
            scroll through.
          </p>
        </div>
      </section>

      <section className="band">
        <div className="wrap">
          <div className="max-w-[860px]">
          <h2 className="text-h3 mb-3">Why it exists</h2>
          <P>
            Finding work from the Philippines means reading the same kinds of
            postings across job sites, most of which you cannot get: the wrong country, a
            timezone you cannot cover, twice your years, or a tool you have
            never touched. The time goes into reading postings, not applying.
          </P>
          <P>
            So this does the reading. It keeps a pool of live postings, clears out the closed ones every few hours, and scores the
            whole pool against your resume when you ask it to. You get the
            short list worth applying to, and the ones that came close with
            the reason attached.
          </P>

          <h2 className="text-h3 mb-3 mt-9">What it will not do</h2>
          <P>
            It will not share your resume with employers, sell your data, or
            charge you on a subscription. It does not apply for you, and it
            does not promise a job. It tells you where your applications are
            most likely to land.
          </P>

          <h2 className="text-h3 mb-3 mt-9">Contact</h2>
          <P>
            Questions, suggestions, a posting that should not be there, or a
            run that went wrong:{" "}
            <a href={`mailto:${CONTACT_EMAIL}`} className="underline font-bold">
              {CONTACT_EMAIL}
            </a>
            .
          </P>

          <div className="flex gap-3 flex-wrap mt-8">
            <Link href="/how-it-works" className="btn btn-paper">How it works</Link>
            <Link href="/signup" className="btn">Try it free</Link>
          </div>
          </div>
        </div>
      </section>
    </main>
  );
}
