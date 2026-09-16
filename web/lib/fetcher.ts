/**
 * The fetcher behind every useSWR poll. A non-2xx response throws with its
 * status attached, so a poll can tell "no such thing" (401/404, stop) from a
 * blip (5xx, SWR retries it).
 */
export class HttpError extends Error {
  constructor(public status: number) {
    super(`HTTP ${status}`);
  }
}

export async function fetchJson(url: string) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new HttpError(r.status);
  return r.json();
}
