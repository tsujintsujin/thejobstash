import { getCloudflareContext } from "@opennextjs/cloudflare";

/**
 * Access to the Worker's bindings and secrets.
 *
 * Everything Cloudflare hands the app - the D1 database, the R2 bucket, the
 * tunnel's URL and shared secret - arrives on one `env` object rather than
 * through `process.env`, because bindings are live objects and cannot be
 * serialised into environment variables. This is the single place that object
 * is reached for, so the rest of the app never imports the adapter directly.
 */
export type Env = {
  DB: D1Database;
  /** Absent until the R2 subscription is added; callers must cope. */
  DIGESTS?: R2Bucket;
  JOBSTASH_PY_ORIGIN?: string;
  JOBSTASH_PY_TOKEN?: string;
  JOBSTASH_GOOGLE_CLIENT_ID?: string;
  JOBSTASH_GOOGLE_CLIENT_SECRET?: string;
  JOBSTASH_GOOGLE_REDIRECT_URI?: string;
  JOBSTASH_GOOGLE_STUB_ORIGIN?: string;
  /** PayMongo secret key - `wrangler secret put`, never in a file. */
  PAYMONGO_SECRET_KEY?: string;
  /** Resend API key for sign-up codes - a secret. The same name mailer.py reads. */
  JOBSTASH_RESEND_KEY?: string;
  /** Sender, on a domain verified in Resend: `TheJobStash <noreply@thejobstash.com>`. */
  JOBSTASH_FROM?: string;
};

export function env(): Env {
  return getCloudflareContext().env as unknown as Env;
}

/**
 * A named var, or undefined. Falls back to `process.env` so `next dev` picks
 * values out of .env.local the way it always did - wrangler's vars are not
 * loaded when the plain dev server is what is running.
 */
export function envVar(name: keyof Env): string | undefined {
  let v: unknown;
  try {
    v = env()[name];
  } catch {
    // Outside a request (a build-time import, say) there is no context.
    v = undefined;
  }
  return (typeof v === "string" && v) || process.env[name as string] || undefined;
}
