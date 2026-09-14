import type { Metadata } from "next";
import { LegalBody, LegalHeader } from "@/app/legal/shell";
import { TERMS, TERMS_SUMMARY } from "@/app/legal/terms";

export const metadata: Metadata = {
  title: "Terms of Service — TheJobStash",
  description:
    "The agreement for using TheJobStash: what the service promises, what it " +
    "explicitly does not, and what happens when either of us walks away.",
};

export default function TermsPage() {
  return (
    <main>
      <LegalHeader
        title="Terms of Service"
        lede="What the service promises, what it explicitly does not, and what happens if either of us walks away. Short, because a contract nobody reads is not more binding than a plain one they do."
      />
      <LegalBody
        summary={TERMS_SUMMARY}
        sections={TERMS}
        otherHref="/privacy"
        otherLabel="the Privacy Policy"
      />
    </main>
  );
}
