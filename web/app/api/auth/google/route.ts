import { NextRequest, NextResponse } from "next/server";
import crypto from "node:crypto";
import { cookies } from "next/headers";
import { safeNext } from "@/lib/session";
import {
  googleConfigured,
  googleClient,
  googleRedirectUri,
  googleAuthEndpoint,
  GOOGLE_SCOPES,
} from "@/lib/google";

/**
 * Step one: bounce the visitor to Google.
 *
 * `state` is a random value stored in a short-lived httpOnly cookie and
 * checked on the way back. Without it, an attacker can feed someone a
 * pre-baked callback URL and land them in the attacker's account - the login
 * equivalent of CSRF. The post-login destination rides inside the same cookie
 * rather than in `state` itself, so nothing user-controlled makes the trip.
 */
export async function GET(req: NextRequest) {
  if (!googleConfigured()) {
    return NextResponse.json(
      { error: "Google sign-in isn't configured on this server yet." },
      { status: 503 }
    );
  }

  const state = crypto.randomBytes(16).toString("hex");
  const next = safeNext(req.nextUrl.searchParams.get("next"));

  // `state` is fixed-width hex, so splitting on the FIRST colon is what
  // keeps a path that legitimately contains one (`/x:y`) intact on the way
  // back. Splitting on every colon silently truncated the destination.
  (await cookies()).set("jobstash_oauth", `${state}:${next}`, {
    httpOnly: true,
    sameSite: "lax", // must survive Google's top-level redirect back
    path: "/",
    maxAge: 600,
    secure: process.env.NODE_ENV === "production",
  });
  const u = new URL(googleAuthEndpoint());
  u.searchParams.set("client_id", googleClient().id);
  u.searchParams.set("redirect_uri", googleRedirectUri());
  u.searchParams.set("response_type", "code");
  u.searchParams.set("scope", GOOGLE_SCOPES);
  u.searchParams.set("state", state);
  // Ask for an account choice every time. Silently reusing whichever Google
  // account the browser happens to hold is how people end up with a second
  // stash they did not mean to create.
  u.searchParams.set("prompt", "select_account");
  return NextResponse.redirect(u.toString());
}
