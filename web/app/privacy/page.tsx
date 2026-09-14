import type { Metadata } from "next";
import { LegalBody, LegalHeader } from "@/app/legal/shell";
import { PRIVACY, PRIVACY_SUMMARY } from "@/app/legal/privacy";

export const metadata: Metadata = {
  title: "Privacy Policy — TheJobStash",
  description:
    "What TheJobStash collects, why, who it goes to, how long it is kept, " +
    "and how to get it deleted. Written against what the code actually does.",
};

export default function PrivacyPage() {
  return (
    <main>
      <LegalHeader
        title="Privacy Policy"
        lede="What is collected, why, who else sees it, and how to get rid of it — written against what the code does, in language that does not need a lawyer."
      />
      <LegalBody
        summary={PRIVACY_SUMMARY}
        sections={PRIVACY}
        otherHref="/terms"
        otherLabel="the Terms of Service"
      />
    </main>
  );
}
