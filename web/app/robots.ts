import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

// Everything behind a sign-in stays out: crawling it only ever yields the
// redirect to /signup. AI crawlers are allowed here; whether they can reach
// the site at all is Cloudflare's bot setting, not this file.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/api/", "/dashboard", "/upload", "/login"],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
