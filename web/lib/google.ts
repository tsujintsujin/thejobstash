/**
 * Google sign-in configuration.
 *
 * Deliberately a lookup rather than a module-level constant: the auth card
 * asks `googleConfigured()` at render time and only shows the button when the
 * credentials actually exist. A button that opens Google and comes back with
 * `invalid_client` is worse than no button.
 */
import { envVar } from "./cf";

export const GOOGLE_SCOPES = "openid email profile";

export function googleConfigured() {
  return Boolean(
    envVar("JOBSTASH_GOOGLE_CLIENT_ID") &&
      envVar("JOBSTASH_GOOGLE_CLIENT_SECRET")
  );
}

/**
 * Must match a URI registered on the OAuth client exactly - Google compares
 * the whole string. Overridable so a deployed origin does not need a code
 * change, defaulting to the dev server this project runs on.
 */
export function googleRedirectUri() {
  return (
    envVar("JOBSTASH_GOOGLE_REDIRECT_URI") ||
    "http://localhost:3200/api/auth/google/callback"
  );
}

export function googleClient() {
  return {
    id: envVar("JOBSTASH_GOOGLE_CLIENT_ID") || "",
    secret: envVar("JOBSTASH_GOOGLE_CLIENT_SECRET") || "",
  };
}

/**
 * The two Google endpoints, redirectable at a local stub.
 *
 * Creating a real OAuth client needs a Google Cloud project that only the
 * account owner can make, so without a seam the interesting half of this flow
 * - account creation, linking an existing address, and the refusal to link an
 * unverified one - could never be exercised before shipping. Those are the
 * branches with security consequences, so "we'll find out in production" is
 * not an acceptable test plan for them.
 *
 * The override is refused outright when NODE_ENV is production. A live server
 * that can be told where to go and ask whether a password is correct is a
 * total authentication bypass, and an environment variable is exactly the
 * thing that leaks in from a misapplied deploy config. It fails loudly rather
 * than silently ignoring the value, because a stub quietly not taking effect
 * would mean tests that pass against the real Google and prove nothing.
 */
function stubOrigin(): string {
  const raw = envVar("JOBSTASH_GOOGLE_STUB_ORIGIN");
  if (!raw) return "";
  if (process.env.NODE_ENV === "production") {
    throw new Error(
      "JOBSTASH_GOOGLE_STUB_ORIGIN is set in a production build. This " +
        "redirects Google sign-in at an arbitrary server and would be an " +
        "authentication bypass. Unset it."
    );
  }
  return raw.replace(/\/+$/, "");
}

export function googleAuthEndpoint() {
  const stub = stubOrigin();
  return stub
    ? `${stub}/o/oauth2/v2/auth`
    : "https://accounts.google.com/o/oauth2/v2/auth";
}

export function googleTokenEndpoint() {
  const stub = stubOrigin();
  return stub ? `${stub}/token` : "https://oauth2.googleapis.com/token";
}

/** True when sign-in is pointed at a stub, so the UI can say so out loud. */
export function googleIsStubbed() {
  return Boolean(stubOrigin());
}
