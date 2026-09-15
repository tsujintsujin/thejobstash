import { envVar } from "./cf";

/**
 * One transactional email, through Brevo's transactional API.
 *
 * Without a key, `next dev` prints the message to the server console instead,
 * so sign-up can be exercised locally. A production build without a key
 * throws: telling someone "we emailed you a code" when nothing was sent is a
 * dead end they cannot see.
 *
 * The sender must be on a domain authenticated in Brevo (thejobstash.com), or
 * Brevo rejects the send.
 */
export async function sendMail(to: string, subject: string, text: string, html: string) {
  const key = envVar("JOBSTASH_BREVO_KEY");
  if (!key) {
    if (process.env.NODE_ENV !== "production") {
      console.log(`[mail] JOBSTASH_BREVO_KEY unset, not sent. to=${to} subject="${subject}"\n${text}`);
      return;
    }
    throw new Error("Email is not configured on this server.");
  }
  const res = await fetch("https://api.brevo.com/v3/smtp/email", {
    method: "POST",
    headers: { "api-key": key, "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({
      sender: {
        name: "TheJobStash",
        email: envVar("JOBSTASH_FROM_EMAIL") || "noreply@thejobstash.com",
      },
      to: [{ email: to }],
      subject,
      textContent: text,
      htmlContent: html,
    }),
  });
  if (!res.ok) {
    console.error(`[mail] brevo ${res.status}: ${await res.text().catch(() => "")}`);
    throw new Error("The email could not be sent.");
  }
}
