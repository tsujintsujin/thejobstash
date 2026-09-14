import { envVar } from "./cf";

/**
 * One transactional email, through Resend - the provider mailer.py already
 * uses for digests, under the same JOBSTASH_RESEND_KEY.
 *
 * Without a key, `next dev` prints the message to the server console instead,
 * so sign-up can be exercised locally. A production build without a key
 * throws: telling someone "we emailed you a code" when nothing was sent is a
 * dead end they cannot see.
 */
export async function sendMail(to: string, subject: string, text: string, html: string) {
  const key = envVar("JOBSTASH_RESEND_KEY");
  if (!key) {
    if (process.env.NODE_ENV !== "production") {
      console.log(`[mail] JOBSTASH_RESEND_KEY unset, not sent. to=${to} subject="${subject}"\n${text}`);
      return;
    }
    throw new Error("Email is not configured on this server.");
  }
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      from: envVar("JOBSTASH_FROM") || "TheJobStash <noreply@thejobstash.com>",
      to: [to],
      subject,
      text,
      html,
    }),
  });
  if (!res.ok) {
    console.error(`[mail] resend ${res.status}: ${await res.text().catch(() => "")}`);
    throw new Error("The email could not be sent.");
  }
}
