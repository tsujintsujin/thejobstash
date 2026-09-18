import { NextResponse, type NextRequest } from "next/server";

// http://thejobstash.com and http://www served the page instead of redirecting,
// so each page existed at three addresses. Cloudflare's own rule only covers
// https://www. One permanent hop to the canonical origin fixes both.
// Only an explicit http signal redirects: with no header we pass through, so a
// missing header can never turn into a redirect loop.
export function middleware(req: NextRequest) {
  const host = req.headers.get("host") ?? "";
  // cf-visitor is set by Cloudflare's edge from the visitor's real scheme.
  // x-forwarded-proto is not trusted: Next's own server fills it in.
  const http = (req.headers.get("cf-visitor") ?? "").includes('"scheme":"http"');
  if (host === "www.thejobstash.com" || (host === "thejobstash.com" && http)) {
    const url = new URL(req.nextUrl.pathname + req.nextUrl.search, "https://thejobstash.com");
    return NextResponse.redirect(url, 301);
  }
}

export const config = {
  matcher: "/((?!_next/static|_next/image).*)",
};
