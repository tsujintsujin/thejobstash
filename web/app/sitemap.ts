import type { MetadataRoute } from "next";
import { poolPages } from "@/lib/db";
import { SITE_URL } from "@/lib/site";

// Read per request: the /jobs pages come and go with the pool, and a sitemap
// that lists a 404 is one Search Console complains about.
export const dynamic = "force-dynamic";

const STATIC: [string, number][] = [
  ["/", 1],
  ["/jobs", 0.9],
  ["/how-it-works", 0.8],
  ["/about", 0.6],
  ["/signup", 0.6],
  ["/privacy", 0.2],
  ["/terms", 0.2],
  ["/refunds", 0.2],
];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const out: MetadataRoute.Sitemap = STATIC.map(([path, priority]) => ({
    url: SITE_URL + path,
    priority,
  }));
  try {
    for (const p of await poolPages()) {
      out.push({
        url: `${SITE_URL}/jobs/${p.slug}`,
        lastModified: p.updated_at,
        changeFrequency: "daily",
        priority: 0.8,
      });
    }
  } catch {
    // D1 unreachable: still serve the static pages rather than a 500.
  }
  return out;
}
