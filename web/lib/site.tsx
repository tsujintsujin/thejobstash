import type { Metadata } from "next";

/**
 * The site's public identity, for metadata, the sitemap and JSON-LD.
 *
 * The bare domain is the canonical host. www serves the same Worker, so every
 * page names this one explicitly or Google indexes two copies of the site.
 */
export const SITE_URL = "https://thejobstash.com";
export const SITE_NAME = "TheJobStash";
export const SITE_TAGLINE = "Jobs that actually match your resume";
export const SITE_DESCRIPTION =
  "Upload your resume once. Each run scores thousands of live job postings " +
  "from 13 boards against it, remote and Philippine roles alike, and hands " +
  "you the handful worth applying to, plus the ones that came close and why.";

const OG_IMAGE = {
  url: "/opengraph-image.png",
  width: 1200,
  height: 630,
  alt: "TheJobStash: jobs that actually match your resume. First run free.",
};

/**
 * One page's metadata. Every indexable page goes through this so none can
 * ship without a canonical. Next replaces a parent's `openGraph` wholesale
 * rather than merging it, hence siteName and locale repeated here.
 */
export function pageMeta(p: {
  title: string;
  description: string;
  path: string;
  /** Skip the " — TheJobStash" suffix, for a title that already has the brand. */
  absolute?: boolean;
}): Metadata {
  return {
    title: p.absolute ? { absolute: p.title } : p.title,
    description: p.description,
    alternates: { canonical: p.path },
    openGraph: {
      type: "website",
      siteName: SITE_NAME,
      locale: "en_PH",
      url: p.path,
      title: p.title,
      description: p.description,
      // Named explicitly: a page that sets openGraph drops the file-based
      // app/opengraph-image.png it would otherwise inherit.
      images: [OG_IMAGE],
    },
    twitter: {
      card: "summary_large_image",
      title: p.title,
      description: p.description,
      images: [OG_IMAGE.url],
    },
  };
}

/** JSON-LD in a script tag. `<` is escaped so a string in the data can never
 *  close the tag early. */
export function JsonLd({ data }: { data: object }) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{
        __html: JSON.stringify(data).replace(/</g, "\\u003c"),
      }}
    />
  );
}
