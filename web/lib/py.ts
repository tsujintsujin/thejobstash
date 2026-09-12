import { envVar } from "./cf";

/**
 * Call the scorer and parse its JSON.
 *
 * This used to `spawn()` a Python process. Workers cannot start one, so the
 * same commands are now served over HTTP by `py_server.py`, reached through a
 * Cloudflare Tunnel. The JSON contract is unchanged, which is the point:
 * everything that needs the matcher, the resume parser or the renderer still
 * goes through one implementation rather than a TypeScript reimplementation
 * drifting away from the Python one.
 *
 * The tunnel dials out from that machine, so nothing is listening for inbound
 * connections there - the property the original architecture was built on.
 */
export type PyResult = { ok: boolean; error?: string; [k: string]: any };

/** What the user is told when the machine running the scorer is not up. */
const OFFLINE =
  "The scorer is offline right now. This is the one piece that still runs " +
  "on a home machine - try again shortly.";

function config() {
  const origin = envVar("JOBSTASH_PY_ORIGIN");
  const token = envVar("JOBSTASH_PY_TOKEN");
  if (!origin || !token) return null;
  return { origin: origin.replace(/\/+$/, ""), token };
}

async function call(
  path: string,
  init: RequestInit,
  timeoutMs: number
): Promise<PyResult> {
  const cfg = config();
  if (!cfg) {
    console.error("[py] JOBSTASH_PY_ORIGIN / JOBSTASH_PY_TOKEN are not set");
    return { ok: false, error: OFFLINE };
  }

  // A hung tunnel must not hold the request open until the Worker's own
  // wall-clock limit kills it with no explanation.
  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), timeoutMs);

  try {
    const res = await fetch(cfg.origin + path, {
      ...init,
      signal: abort.signal,
      headers: {
        ...(init.headers || {}),
        Authorization: `Bearer ${cfg.token}`,
      },
    });

    const text = await res.text();
    try {
      return JSON.parse(text) as PyResult;
    } catch {
      // Not JSON: almost always the tunnel's own error page rather than the
      // scorer. Log the body, tell the browser nothing about it.
      console.error(
        `[py] ${path} returned non-JSON (HTTP ${res.status}): ${text.slice(0, 500)}`
      );
      return {
        ok: false,
        error:
          res.status === 401
            ? "The scorer rejected this server's credentials."
            : OFFLINE,
      };
    }
  } catch (e: any) {
    const aborted = e?.name === "AbortError";
    console.error(`[py] ${path} failed: ${aborted ? "timed out" : e?.message || e}`);
    return {
      ok: false,
      error: aborted ? "The scorer timed out. Try again." : OFFLINE,
    };
  } finally {
    clearTimeout(timer);
  }
}

/**
 * `parse` and `trial`: the resume goes up as the raw request body.
 *
 * No temp file on this side any more - there is no disk on a Worker, and
 * there is no longer a reason to want one. The bytes are forwarded and
 * forgotten; the far end writes them to its own temp dir and deletes them in
 * a finally block.
 */
export async function pyFile(
  cmd: "parse" | "trial",
  file: File,
  timeoutMs = 180000
): Promise<PyResult> {
  return call(
    `/${cmd}?name=${encodeURIComponent(file.name)}`,
    {
      method: "POST",
      body: await file.arrayBuffer(),
      headers: { "Content-Type": "application/octet-stream" },
    },
    timeoutMs
  );
}

/** `preview` and `deliver`: everything they need is already in the database. */
export async function pyUser(
  cmd: "preview" | "deliver",
  userId: string,
  timeoutMs = 180000
): Promise<PyResult> {
  return call(
    `/${cmd}`,
    {
      method: "POST",
      body: JSON.stringify({ user_id: userId }),
      headers: { "Content-Type": "application/json" },
    },
    timeoutMs
  );
}
