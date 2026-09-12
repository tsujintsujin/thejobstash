import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  eslint: { ignoreDuringBuilds: true },
  // There is an unrelated Next 14 project at the workspace root. Pinning the
  // tracing root here stops the bundler walking up into it and resolving the
  // wrong copy of Next.
  outputFileTracingRoot: __dirname,
};

export default nextConfig;
