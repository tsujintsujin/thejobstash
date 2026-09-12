import { defineCloudflareConfig } from "@opennextjs/cloudflare";

/**
 * Next.js on Workers.
 *
 * No incremental cache configured on purpose: every page this app serves is
 * either static or `force-dynamic` (the dashboard and the auth card both read
 * per-user rows), so there is nothing an ISR cache would hold. Adding a KV
 * namespace to cache nothing is a binding to maintain and a bill to read.
 */
export default defineCloudflareConfig();
