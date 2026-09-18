import type { NextConfig } from "next";
import { initOpenNextCloudflareForDev } from "@opennextjs/cloudflare";

// Gives `next dev` the Worker's bindings (a local D1 under .localdb/), so
// pages that read the database render locally instead of throwing. Run
// `npm run d1:local` once to create its tables.
initOpenNextCloudflareForDev({ persist: { path: ".localdb/v3" } });

const nextConfig: NextConfig = {
  eslint: { ignoreDuringBuilds: true },
  // There is an unrelated Next 14 project at the workspace root. Pinning the
  // tracing root here stops the bundler walking up into it and resolving the
  // wrong copy of Next.
  outputFileTracingRoot: __dirname,
  // No reason to advertise the framework in every response header.
  poweredByHeader: false,
  // No page here is meant to be framed. Without these, another site could lay
  // the dashboard under a decoy and have a signed-in user press Run or Buy.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Strict-Transport-Security", value: "max-age=31536000" },
        ],
      },
    ];
  },
};

export default nextConfig;
