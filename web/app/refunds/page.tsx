import type { Metadata } from "next";
import Link from "next/link";
import {
  LegalBody,
  LegalHeader,
  Note,
  P,
  Rows,
  Section,
  CONTACT_EMAIL,
} from "@/app/legal/shell";

export const metadata: Metadata = {
  title: "Refund Policy — TheJobStash",
  description:
    "When a run is refunded: automatically if it fails, and on request if the " +
    "digest file you were sent is broken.",
};

const MAIL = (
  <a href={`mailto:${CONTACT_EMAIL}`} className="underline">
    {CONTACT_EMAIL}
  </a>
);

const SECTIONS: Section[] = [
  {
    id: "broken",
    title: "A broken file is refunded",
    body: (
      <>
        <Note>
          If the digest file we send you is broken, you get that run back.
        </Note>
        <P>A digest counts as broken when:</P>
        <Rows
          rows={[
            ["The PDF will not open", "or opens as an error, a blank page or garbage."],
            ["Parts of it are missing", "pages cut off, or jobs listed with no details."],
            ["You cannot get the file at all", "the View or PDF button fails for a digest the dashboard says is ready."],
          ]}
        />
      </>
    ),
  },
  {
    id: "failed",
    title: "A failed run needs no request",
    body: (
      <P>
        A credit is taken when a run starts. If the run fails or never starts,
        that credit goes back on your account automatically — you do not need
        to email anyone. If it has not come back within an hour, email {MAIL}.
      </P>
    ),
  },
  {
    id: "not",
    title: "What is not a broken file",
    body: (
      <>
        <P>
          The run did its work in these cases, so the credit stays used. The{" "}
          <Link href="/terms#nopromise" className="underline">
            Terms
          </Link>{" "}
          explain why.
        </P>
        <Rows
          rows={[
            ["Few or no matches", "a short, honest digest is the intended result."],
            ["Matches you did not like", "the scorer makes a judgement call, and shows its reasons."],
            ["A listing that turned out filled, stale or fake", "the listings belong to the boards they came from."],
            ["No job or interview came of it", ""],
          ]}
        />
      </>
    ),
  },
  {
    id: "how",
    title: "How to ask",
    body: (
      <>
        <P>
          Email {MAIL} from the address on your account, say which digest it
          is (its date is enough), and what is wrong with it. A screenshot
          helps.
        </P>
        <P>
          Once it is confirmed broken, the credit that run used goes back on
          your account. If you would rather have the money, say so within 30 days of buying
          the pack, and what you paid for that credit is returned through
          PayMongo to the bank or e-wallet you paid from. After 30 days PayMongo
          can no longer refund the payment, so the credit is the refund.
        </P>
      </>
    ),
  },
];

export default function RefundsPage() {
  return (
    <main>
      <LegalHeader
        title="Refund Policy"
        lede="When a run gets refunded, and how to ask. Short, because the rule is simple."
      />
      <LegalBody
        summary={
          <>
            <p className="mb-2">
              A run that fails hands its credit back on its own.
            </p>
            <p>
              A run that works but sends you a broken file is refunded too —
              email {CONTACT_EMAIL} and say which digest. A run that simply
              found little is not a broken file.
            </p>
          </>
        }
        sections={SECTIONS}
        otherHref="/terms"
        otherLabel="the Terms of Service"
      />
    </main>
  );
}
