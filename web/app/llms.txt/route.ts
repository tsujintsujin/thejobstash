import { PACKS, FREE_CREDITS } from "@/lib/packs";
import { SITE_URL } from "@/lib/site";

// A plain-text summary for AI assistants. Google ignores it; some AI tools
// read it. Prices come from packs.ts so this can never quote a stale one.
export const dynamic = "force-static";

export function GET() {
  const packs = PACKS.map((p) => `${p.credits} runs for PHP ${p.php}`).join(", ");
  const body = `# TheJobStash

> A job matcher for people in the Philippines. Upload a resume once; each run scores thousands of live job postings against it and returns the ones worth applying to, plus the near-misses and exactly what blocked each one.

- Covers remote roles open to people in the Philippines and local Philippine roles.
- Closed postings are cleared out every few hours.
- What a run checks: skills, seniority, location, work authorisation and timezone.
- Pricing: every account starts with ${FREE_CREDITS} free run. After that, credit packs: ${packs}. One credit is one run. No subscription; credits do not expire. Payment by QR Ph (GCash, Maya, bank apps).
- Resumes are never shared with employers.
- Operated by TSUJIN IT SOLUTIONS.

## Pages

- [Home](${SITE_URL}/): what it is and pricing
- [How it works](${SITE_URL}/how-it-works): how postings are gathered, checked and scored
- [Jobs by role](${SITE_URL}/jobs): live counts and example postings per kind of work
- [About](${SITE_URL}/about): who runs it
- [Privacy](${SITE_URL}/privacy), [Terms](${SITE_URL}/terms), [Refunds](${SITE_URL}/refunds)
`;
  return new Response(body, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
