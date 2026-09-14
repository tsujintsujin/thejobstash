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
  EFFECTIVE,
  OPERATOR,
} from "@/app/legal/shell";

export const metadata: Metadata = {
  title: "Terms of Service — TheJobStash",
  description:
    "The agreement for using TheJobStash: what the service promises, what it " +
    "explicitly does not, and what happens when either of us walks away.",
};

/**
 * The companion to /privacy. Two reasons this exists rather than a privacy
 * page alone:
 *
 *   1. Google's OAuth consent screen asks for a terms URL as well as a privacy
 *      URL before it will verify an app, and sign-in is already built.
 *   2. The service reads listings scraped from other people's boards and sends
 *      them on. The disclaimers in "What this does not promise" are the ones
 *      that actually matter here, and there is nowhere else to put them.
 *
 * Kept deliberately short. A ten-thousand-word contract nobody reads is not
 * more binding than a plain one they do.
 */
const SECTIONS: Section[] = [
  {
    id: "agreement",
    title: "The agreement",
    body: (
      <>
        <P>
          These terms are between you and {OPERATOR}, which builds and runs
          TheJobStash. Using the site, creating an
          account or uploading a resume means you accept them. If you do not,
          the remedy is simple and free: do not use the service.
        </P>
        <P>
          The{" "}
          <Link href="/privacy" className="underline">
            Privacy Policy
          </Link>{" "}
          is part of this agreement and explains what happens to your data. It
          is worth the five minutes.
        </P>
      </>
    ),
  },
  {
    id: "service",
    title: "What the service does",
    body: (
      <>
        <P>
          TheJobStash sweeps public job boards into a shared pool, scores that
          pool against the resume you upload each time you run it, and hands
          you the listings that matched — along with the ones that came close and the
          reason each of those fell short.
        </P>
        <P>That is the whole of it. In particular, it does not:</P>
        <Rows
          rows={[
            ["Apply to jobs on your behalf", "you do that yourself, at the employer."],
            ["Send your resume to anybody", "it never leaves the server as a file."],
            ["Contact employers or recruiters for you", ""],
            ["Write, rewrite or review your resume", ""],
            ["Give careers, immigration or legal advice", ""],
          ]}
        />
      </>
    ),
  },
  {
    id: "beta",
    title: "It is in testing, and runs cost credits",
    body: (
      <>
        <Note>
          Every account starts with one free credit. After that, credits are
          bought in packs through PayMongo. There is no subscription and nothing
          recurs: you are charged once, when you buy a pack.
        </Note>
        <P>
          One credit is one run of your resume — the boards swept, the postings
          scored, a digest produced. The credit is taken when the run starts,
          and handed back automatically if the run fails. A run that works but
          finds little still uses its credit, because the sweep and the scoring
          happened. Credits do not expire. A digest file that arrives broken is refunded
          too; the{" "}
          <Link href="/refunds" className="underline">
            Refund Policy
          </Link>{" "}
          explains how.
        </P>
        <P>
          The product is being built in the open. Features change and the
          service can go down without notice. The thing you are using is not a
          finished, guaranteed product, and it would be dishonest to write these
          terms as though it were.
        </P>
        <P>
          Payments are processed by PayMongo, so card and e-wallet details go to
          them, not to us. Prices are shown before you pay, and a price change
          never affects credits you already hold.
        </P>
      </>
    ),
  },
  {
    id: "account",
    title: "Your account",
    body: (
      <>
        <Rows
          rows={[
            [
              "You need to be 16 or over",
              "and the details you sign up with should be real ones — an address you can actually receive a digest at, in particular.",
            ],
            [
              "Your sign-in is yours",
              "keep your password to yourself and do not let other people use your account. Anything done through it is treated as done by you.",
            ],
            [
              "One person, one account",
              "the free credit is one per person; do not work around it by farming accounts.",
            ],
            [
              "Tell us if it is compromised",
              <>
                email{" "}
                <a href={`mailto:${CONTACT_EMAIL}`} className="underline">
                  {CONTACT_EMAIL}
                </a>{" "}
                and the sessions on it will be revoked.
              </>,
            ],
          ]}
        />
      </>
    ),
  },
  {
    id: "content",
    title: "Your resume stays yours",
    body: (
      <>
        <P>
          You keep every right you have in your resume. Uploading it grants a
          narrow, revocable permission to do the specific things the service
          needs: store the extracted text, derive a matching profile from it,
          score it against job listings, and render the results into the digest
          sent to you.
        </P>
        <P>
          That permission covers nothing else. It is not a licence to publish
          it, sell it, share it, or train a model on it, and it ends when you
          delete the resume or the account.
        </P>
        <P>
          You are confirming the resume is yours to upload — do not upload
          somebody else&rsquo;s CV, or a document you are not allowed to share.
        </P>
      </>
    ),
  },
  {
    id: "use",
    title: "How not to use it",
    body: (
      <>
        <P>Do not:</P>
        <Rows
          rows={[
            [
              "Hammer it",
              "no scripted scanning in a loop, no bulk automated requests, nothing designed to make the scorer run more than a person reasonably would.",
            ],
            [
              "Resell the output",
              "the digests are for your own job search. Scraping, republishing or reselling them as a jobs feed is not on.",
            ],
            [
              "Break into it",
              "no probing for holes, no attempts to reach another user's account or data, no bypassing the rate limits or the credit system.",
            ],
            [
              "Upload things that are not resumes",
              "particularly not malware, and not other people's personal data.",
            ],
            ["Use it for anything unlawful", ""],
          ]}
        />
        <P>
          Good-faith security research is welcome and will not be treated as a
          breach of this section — report what you find to the address at the
          bottom rather than to anyone else, and give a reasonable window for it
          to be fixed.
        </P>
      </>
    ),
  },
  {
    id: "nopromise",
    title: "What this does not promise",
    body: (
      <>
        <P>
          The listings come from other people&rsquo;s job boards, which means
          their accuracy is theirs and not ours. A posting can be filled,
          withdrawn, expired, duplicated, mis-titled or fake by the time it
          reaches you, and no amount of scoring on this end fixes a bad
          listing on that one. Check anything before you act on it, and treat a
          listing that asks you for money or personal documents up front with
          the suspicion it deserves.
        </P>
        <Rows
          rows={[
            [
              "No guarantee of a job",
              "or an interview, or a reply. The service surfaces openings that fit your resume. What happens after that is between you and the employer.",
            ],
            [
              "No guarantee the matching is right",
              "the scorer is a piece of software making a judgement call. It will occasionally rank something oddly, or miss a role you would have wanted. That is why the near-misses and the reasons they were blocked are shown rather than hidden.",
            ],
            [
              "No guarantee of a given number of matches",
              "some runs find little that fits. A short honest digest is the intended behaviour, not a fault.",
            ],
            [
              "No guarantee of uptime or delivery",
              "the scrape can fail, a board can change its markup, an email can land in spam.",
            ],
          ]}
        />
        <P>
          Put in the language these documents usually use: the service is
          provided &ldquo;as is&rdquo; and &ldquo;as available&rdquo;, without
          warranties of any kind, express or implied, including any implied
          warranty of merchantability, fitness for a particular purpose or
          non-infringement.
        </P>
      </>
    ),
  },
  {
    id: "liability",
    title: "Liability",
    body: (
      <>
        <P>
          To the fullest extent the law allows, neither {OPERATOR} nor anyone
          working on TheJobStash is liable for indirect or consequential loss —
          a job you did not get, an opportunity you missed, income you did not
          earn, or data you did not keep a copy of elsewhere.
        </P>
        <P>
          Where liability cannot be excluded, it is capped at whatever you have
          actually paid for the service in the twelve months before the claim.
          In practice that is what you paid for credit packs in that period,
          and it would be dishonest to imply the cap is anything larger.
        </P>
        <P>
          None of this limits anything that cannot be limited by law: death or
          personal injury caused by negligence, fraud, or the consumer rights
          your own country gives you and does not let anyone sign away.
        </P>
      </>
    ),
  },
  {
    id: "ending",
    title: "Ending it",
    body: (
      <>
        <P>
          You can stop at any time. Email the address below and your resume, or
          the whole account and everything attached to it, is deleted — there
          is nothing to cancel and no notice period, because there is nothing
          being charged.
        </P>
        <P>
          Access may be suspended or removed from this end if an account is
          being used to break the rules in{" "}
          <a href="#use" className="underline">
            How not to use it
          </a>
          , or if it is putting the service at risk for everyone else. Where
          there is any reasonable way to warn you first, you will be warned
          first. If the service is ever shut down entirely, account holders get
          notice and a chance to export what is theirs.
        </P>
      </>
    ),
  },
  {
    id: "ip",
    title: "The site itself",
    body: (
      <P>
        The design, the code, the wording and the name TheJobStash belong to{" "}
        {OPERATOR}. Using the service does not transfer any of that to you. Job
        listings are the property of whoever posted them, and are passed on to
        you as found.
      </P>
    ),
  },
  {
    id: "changes",
    title: "Changes to these terms",
    body: (
      <P>
        These terms may change as the product does. The date at the top always
        says which version is current, and anything that materially affects your
        rights will be emailed to account holders before it takes effect.
        Continuing to use the service after a change means you accept the new
        version; if you do not, delete the account.
      </P>
    ),
  },
  {
    id: "law",
    title: "Governing law",
    body: (
      <P>
        These terms are governed by the laws of the Republic of the Philippines,
        and its courts have jurisdiction over any dispute. If you are a consumer
        somewhere else, this does not take away the protections of your own
        country&rsquo;s law, or your right to bring a claim in your local
        courts where that law says you can.
      </P>
    ),
  },
  {
    id: "contact",
    title: "Contact",
    body: (
      <>
        <P>
          Anything at all about these terms, including a dispute, goes to a
          person at:
        </P>
        <P>
          <a
            href={`mailto:${CONTACT_EMAIL}`}
            className="font-extrabold underline"
          >
            {CONTACT_EMAIL}
          </a>
        </P>
        <P>
          Talking first is genuinely faster than anything else on this page. In
          effect {EFFECTIVE}.
        </P>
      </>
    ),
  },
];

export default function TermsPage() {
  return (
    <main>
      <LegalHeader
        title="Terms of Service"
        lede="What the service promises, what it explicitly does not, and what happens if either of us walks away. Short, because a contract nobody reads is not more binding than a plain one they do."
      />
      <LegalBody
        summary={
          <>
            <p className="mb-2">
              We score public job listings against your resume and hand you the ones that fit. We do not apply for you, and we cannot promise you
              a job — the listings are other people&rsquo;s and some of them
              will be stale or wrong, so check before you act.
            </p>
            <p className="mb-2">
              It is in testing. Runs cost credits bought through PayMongo; your
              first is free, nothing recurs, and nothing is guaranteed to be up.
            </p>
            <p>
              Your resume stays yours. Do not hammer the service or resell the
              digests, and you can walk away and have everything deleted
              whenever you like.
            </p>
          </>
        }
        sections={SECTIONS}
        otherHref="/privacy"
        otherLabel="the Privacy Policy"
      />
    </main>
  );
}
