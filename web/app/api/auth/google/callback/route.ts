import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import {
  userByEmail,
  userByGoogleSub,
  createOAuthUser,
  linkGoogleSub,
  grantPlan,
} from "@/lib/db";
import { createSession, safeNext } from "@/lib/session";
import {
  googleConfigured,
  googleClient,
  googleRedirectUri,
  googleTokenEndpoint,
} from "@/lib/google";

/** Everything that can go wrong lands back on the card with a readable line. */
function bounce(origin: string, message: string) {
  return NextResponse.redirect(
    `${origin}/signup?mode=signin&err=${encodeURIComponent(message)}`
  );
}

export async function GET(req: NextRequest) {
  const origin = req.nextUrl.origin;
  const jar = await cookies();
  const raw = jar.get("jobstash_oauth")?.value || "";
  jar.delete("jobstash_oauth"); // single use, whatever happens below

  if (!googleConfigured()) return bounce(origin, "Google sign-in isn't set up yet.");

  const params = req.nextUrl.searchParams;
  // The visitor pressed Cancel on Google's screen. Not an error worth shouting.
  if (params.get("error")) return NextResponse.redirect(`${origin}/signup?mode=signin`);

  const code = params.get("code") || "";
  // Split on the FIRST colon only. `raw.split(":")` dropped everything after
  // a second one, so a destination that legitimately contains a colon came
  // back truncated - and a truncated path is still a valid-looking path, so
  // it redirected somewhere real instead of failing visibly.
  const cut = raw.indexOf(":");
  const state = cut === -1 ? "" : raw.slice(0, cut);
  const storedNext = cut === -1 ? "/dashboard" : raw.slice(cut + 1) || "/dashboard";
  if (!code || !state || state !== params.get("state")) {
    return bounce(origin, "That sign-in link expired. Please try again.");
  }

  // Exchange the one-time code for tokens. This is a server-to-server call
  // carrying the client secret, which is why it cannot happen in the browser.
  const tokenRes = await fetch(googleTokenEndpoint(), {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      code,
      client_id: googleClient().id,
      client_secret: googleClient().secret,
      redirect_uri: googleRedirectUri(),
      grant_type: "authorization_code",
    }),
  });
  if (!tokenRes.ok) return bounce(origin, "Google turned that sign-in down. Please try again.");

  const { id_token } = (await tokenRes.json()) as { id_token?: string };
  if (!id_token) return bounce(origin, "Google didn't return an identity. Please try again.");

  // The id_token came straight from Google's token endpoint over TLS, so its
  // signature is already vouched for by the channel and the claims can be
  // read directly. Do NOT reuse this shortcut for a token arriving from a
  // browser - that one has to be verified against Google's JWKS first.
  const claims = JSON.parse(
    Buffer.from(id_token.split(".")[1], "base64url").toString("utf8")
  ) as { sub?: string; email?: string; email_verified?: boolean | string };

  const sub = claims.sub || "";
  const email = String(claims.email || "").trim().toLowerCase();
  const verified = claims.email_verified === true || claims.email_verified === "true";
  if (!sub || !email) return bounce(origin, "Google didn't share an email address.");

  let user = await userByGoogleSub(sub);

  if (!user) {
    const existing = await userByEmail(email);
    if (existing) {
      // Linking by address is only safe when Google says it owns the address.
      // Otherwise anyone who could set an unverified Google email to someone
      // else's would walk straight into their stash.
      if (!verified) {
        return bounce(
          origin,
          "That email already has an account. Sign in with your password."
        );
      }
      await linkGoogleSub(existing.id, sub);
      user = existing;
    } else {
      user = await createOAuthUser(email, sub);
      // Matches the password signup path: payments are off, so the default
      // window is granted immediately. Stripe's webhook writes the same row.
      await grantPlan(user.id, "seven_day");
      await createSession(user.id);
      // A brand new account has no resume, and nothing works until it does.
      return NextResponse.redirect(`${origin}/upload`);
    }
  }

  await createSession(user.id);
  return NextResponse.redirect(`${origin}${safeNext(storedNext)}`);
}
