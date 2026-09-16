import {
  Note,
  P,
  Rows,
  Section,
  CONTACT_EMAIL,
  EFFECTIVE,
  OPERATOR,
} from "./shell";

/**
 * Written from the schema in `db.py` and the routes under `app/api/`, not from
 * a template. Every claim below is one somebody could check by reading the
 * source, which is the only kind worth making:
 *
 *   db.py SCHEMA            users / profiles / sessions /
 *                           deliveries / runs / payments
 *   api/resume/route.ts     temp file, unlinked in `finally`; text is kept
 *   lib/session.ts          the one cookie, httpOnly + lax + secure
 *   lib/google.ts           scopes: openid email profile, and no more
 *   mailer.py               Resend, only when JOBSTASH_RESEND_KEY is set
 *
 * If any of those change, this page changes with them.
 */
export const PRIVACY: Section[] = [
  {
    id: "who",
    title: "Who this is and what it covers",
    body: (
      <>
        <P>
          TheJobStash is run by {OPERATOR}. For data-protection purposes{" "}
          {OPERATOR} is the controller of the information described here, and
          a person there answers the address at the bottom of this page.
        </P>
        <P>
          This policy covers the TheJobStash website, the account area and the job digests produced each time you run your resume. It does not cover the job boards the
          listings are scraped from, or the employer sites you land on after
          clicking a listing — those are other people&rsquo;s services with
          their own policies.
        </P>
        <Note>
          The product is in testing. Credits are bought through PayMongo, which
          runs the checkout itself: card and e-wallet details go to them and
          never reach us. What is kept about a purchase is listed below.
        </Note>
      </>
    ),
  },
  {
    id: "collect",
    title: "What is collected",
    body: (
      <>
        <P>
          Only what the service needs to do the job it advertises. There is no
          analytics package, no advertising network and no third-party tracking
          script anywhere on this site.
        </P>
        <Rows
          rows={[
            [
              "Your email address",
              "so an account can exist and a digest has somewhere to go.",
            ],
            [
              "A password, if you set one",
              "never stored as you typed it. It is salted and hashed with PBKDF2-SHA256 over 100,000 rounds; the original cannot be recovered from what is kept, including by us.",
            ],
            [
              "Your Google account id, if you sign in with Google",
              "the stable subject identifier, plus the email address and basic profile Google returns. Nothing else — the request asks for openid, email and profile and no other scope, so there is no access to your Gmail, your Drive or your contacts.",
            ],
            ["Your resume", "in the form described in the next section."],
            [
              "Your digests",
              "the date of each digest, its match and near-miss counts, and whether the email went out.",
            ],
            [
              "Your credits and purchases",
              "your credit balance, each run and whether it finished, and for each pack you buy: its size, the amount, PayMongo's checkout reference and when it was paid. No card or e-wallet details — PayMongo holds those.",
            ],
            [
              "A session record",
              "a random token, when it was created and when it expires, matched against the cookie in your browser.",
            ],
          ]}
        />
        <P>
          No field anywhere asks for a date of birth, a phone number, a home
          address, a photograph or a payment method, and none of those are
          inferred.
        </P>
      </>
    ),
  },
  {
    id: "resume",
    title: "Your resume, specifically",
    body: (
      <>
        <P>
          A resume is the most personal thing this service touches, so it is
          worth being exact about what happens to it.
        </P>
        <Rows
          rows={[
            [
              "The file is not kept",
              "the upload is written to a temporary directory, read once, and deleted immediately afterwards — including when the parse fails. It is never written anywhere the web server can serve it, and it is never emailed anywhere.",
            ],
            [
              "The text is kept",
              "the plain text extracted from the file, and the original filename, are stored against your account, so your matches can be re-scored against jobs found next week without asking you to upload it all over again.",
            ],
            [
              "A profile is derived from it",
              "skills, seniority, the places you can work and your work authorisation. That profile is what the scorer actually reads.",
            ],
            [
              "Nothing is sent to an AI service",
              "the parsing and the scoring are ordinary code running on our own server — pattern matching and arithmetic. Your resume is not sent to OpenAI, Anthropic, Google or any other model provider, and it is not used to train anything.",
            ],
            [
              "It is never shown to employers",
              "TheJobStash reads public job listings and sends them to you. It does not apply on your behalf, does not forward your resume, and does not sell or pass your details to recruiters. There is nobody at the other end of this reading your CV.",
            ],
          ]}
        />
        <Note>
          Resumes often carry more than they need to — a date of birth, a
          nationality, a health disclosure, a photograph. None of it helps the
          scoring, so if you would rather it were never stored, take it out of
          the file before uploading. Replacing your resume in the dashboard
          overwrites the stored text and the derived profile outright, and
          deleting it removes both.
        </Note>
      </>
    ),
  },
  {
    id: "why",
    title: "Why, and on what legal basis",
    body: (
      <>
        <P>
          Where the UK or EU GDPR applies to you, these are the grounds relied
          on. Where the Philippines&rsquo; Data Privacy Act of 2012 applies,
          the equivalent grounds are contract, legitimate interest and — for
          the resume itself — your consent, given by uploading it.
        </P>
        <Rows
          rows={[
            [
              "Performance of a contract",
              "your email address, your password or Google id, your resume text and derived profile, your credit balance, purchases and delivery history. These are what the service you asked for is made of; without them there is nothing to deliver.",
            ],
            [
              "Legitimate interests",
              "the session record, and the attempt records behind the sign-in and sign-up limits. Both exist to keep the service standing up: one so you stay signed in, the other so nobody can guess passwords or mass-create accounts. Neither is used to profile you or to advertise to you.",
            ],
            [
              "Consent",
              "for the resume content, which you supply deliberately and can withdraw by deleting it. Withdrawing it stops future digests, because there is then nothing left to score against.",
            ],
          ]}
        />
      </>
    ),
  },
  {
    id: "cookies",
    title: "Cookies",
    body: (
      <>
        <P>
          One cookie. It is called{" "}
          <code className="font-mono text-[13.5px]">jobstash_session</code>, it
          holds a random token and nothing else, and it is what keeps you signed
          in for thirty days. It is set <em>httpOnly</em>, so page scripts
          cannot read it, and <em>SameSite=Lax</em>, so it is not sent along
          with requests started by other sites. In production it is marked{" "}
          <em>Secure</em> and travels only over HTTPS.
        </P>
        <P>
          It is strictly necessary — the site cannot tell who you are without
          it — which is why there is no banner asking permission for something
          you cannot decline and still have an account. Signing out deletes both
          the cookie and the record behind it, so a token copied out of an old
          browser stops working straight away.
        </P>
        <P>
          There are no analytics cookies, no advertising cookies, and no
          cross-site tracking of any kind.
        </P>
      </>
    ),
  },
  {
    id: "sharing",
    title: "Who else sees it",
    body: (
      <>
        <P>
          Your data is not sold, rented, traded or handed to advertisers, data
          brokers, recruiters or lead-generation services, and it is not shared
          for anyone else&rsquo;s marketing. The only third parties involved are
          the ones needed to run the thing:
        </P>
        <Rows
          rows={[
            [
              "Google",
              "only if you choose to sign in with Google. Google tells us your subject id, email address and basic profile; nothing about you goes back the other way, and your resume is never part of that exchange.",
            ],
            [
              "PayMongo",
              "only if you buy credits. PayMongo runs the checkout, so your card or e-wallet details go to them and never reach us. They receive the amount and a reference for the purchase; they do not receive your resume or your digests.",
            ],
            [
              "Resend",
              "the email provider that delivers your digest once live sending is switched on. It receives your email address and the digest itself — your matched listings and the attached PDF. It does not receive your resume file or your stored resume text.",
            ],
            [
              "Cloudflare",
              "hosts the site and the account database, so it necessarily holds that data on its disks. Resume scoring and digest rendering run on our own server.",
            ],
            [
              "Nobody else",
              "no analytics vendor, no CRM, no ad network, no AI model provider.",
            ],
          ]}
        />
        <P>
          Information may also be disclosed where the law genuinely requires it
          — a valid court order, or a lawful request from an authority with the
          standing to make one. If that ever happens and there is no legal bar
          to saying so, you will be told.
        </P>
        <P>
          If the service were ever transferred to someone else, account holders
          would be told before any data moved, and given the chance to delete
          their account first.
        </P>
      </>
    ),
  },
  {
    id: "jobs",
    title: "Where the job listings come from",
    body: (
      <>
        <P>
          Listings are scraped from public job boards into a single shared
          pool every few hours, and a listing a board stops showing is checked
          and removed once it has closed — all without reference to
          anyone&rsquo;s profile. Your resume is then scored against that pool
          on our own server.
        </P>
        <P>
          The consequence is worth stating plainly: the job boards learn nothing
          about you. They are not told that you exist, that you are looking, or
          what your resume says. The scrape looks identical whether you have an
          account or not.
        </P>
      </>
    ),
  },
  {
    id: "retention",
    title: "How long it is kept",
    body: (
      <Rows
        rows={[
          [
            "Uploaded files",
            "minutes at most. Deleted as soon as the text has been read out of them.",
          ],
          [
            "Resume text and derived profile",
            "until you delete the resume, or the account. Uploading a new resume replaces the old one outright.",
          ],
          [
            "Account, credits, purchases and delivery history",
            "until you ask for the account to be deleted.",
          ],
          [
            "Rendered digests",
            "the HTML and PDF of each run are kept on the server so the dashboard can re-open a past digest, and go with the account.",
          ],
          ["Sessions", "thirty days, or until you sign out."],
          [
            "Scraped job listings",
            "kept in the shared pool regardless of who is signed up. These are public postings by companies, not personal data about you.",
          ],
        ]}
      />
    ),
  },
  {
    id: "rights",
    title: "Your rights, and how to actually use them",
    body: (
      <>
        <P>
          Under the UK and EU GDPR, and under the Philippines&rsquo; Data
          Privacy Act, you have the right to see what is held about you, to have
          it corrected, to have it deleted, to restrict or object to how it is
          used, and to receive it in a portable form. Those rights are honoured
          here regardless of where you live — there is no reason to run two
          standards.
        </P>
        <Rows
          rows={[
            [
              "Replace your resume yourself",
              "uploading a new one from the dashboard overwrites the stored text and the derived profile. The old version is not kept alongside it.",
            ],
            [
              "Delete your resume, or the whole account",
              <>
                email{" "}
                <a href={`mailto:${CONTACT_EMAIL}`} className="underline">
                  {CONTACT_EMAIL}
                </a>{" "}
                from the address the account uses, and say which. Deleting the
                resume removes the stored text, the derived profile and your
                delivery history; deleting the account removes those plus the
                account itself, the credit balance and the rendered digests. Both are an
                email rather than a button for now, because the self-service
                controls are not on the dashboard yet — when they are, this
                line changes.
              </>,
            ],
            [
              "Get a copy",
              "ask, and you will be sent the rows held against your account in a readable file.",
            ],
            [
              "Stop the emails",
              "a digest is only produced when you run your resume yourself, so nothing is sent unless you ask for it. Deleting your resume stops them entirely, because there is then nothing to score.",
            ],
          ]}
        />
        <P>
          Requests are answered as fast as one person reasonably can, and within
          thirty days at the outside. There is no charge. If you are unhappy
          with the answer you can complain to a data-protection regulator — the
          ICO in the UK, your national authority in the EU, or the National
          Privacy Commission in the Philippines.
        </P>
      </>
    ),
  },
  {
    id: "security",
    title: "Security",
    body: (
      <>
        <P>
          Passwords are salted and hashed with PBKDF2-SHA256 over 100,000 rounds
          and are never stored or logged in readable form. Sessions are
          server-side records referenced by an httpOnly cookie rather than a
          self-contained token, which means a session can be revoked outright
          instead of merely expiring. Uploads are size-limited, restricted to
          PDF, DOCX, TXT and Markdown, and written outside any web-served
          directory. Sign-in redirects are restricted to paths on this site, so
          a crafted link cannot borrow the domain&rsquo;s credibility to bounce
          you somewhere else.
        </P>
        <P>
          None of that is a guarantee, and anyone offering you one is selling
          something. No system is perfectly secure. If a breach ever affects
          your data you will be told what happened, what was involved and what
          to do about it — rather than waiting to see whether anybody noticed.
        </P>
      </>
    ),
  },
  {
    id: "children",
    title: "Age",
    body: (
      <P>
        TheJobStash is for people looking for work and is not intended for
        anyone under 16. Accounts are not knowingly created for children, and
        any that is found will be deleted. If you believe a child has given us
        their information, email the address below and it will be removed.
      </P>
    ),
  },
  {
    id: "transfers",
    title: "Where the data lives",
    body: (
      <P>
        The service is operated from the Philippines and hosted on
        infrastructure that may sit in another country, and the email provider
        processes messages outside it as well. If you are in the UK or the EEA
        that means your data may be transferred abroad; where it is, the
        transfer relies on the standard contractual clauses those providers
        publish, and the protections in this policy follow it wherever it goes.
      </P>
    ),
  },
  {
    id: "changes",
    title: "Changes to this policy",
    body: (
      <P>
        If this policy changes, the date at the top changes with it. Anything
        that materially affects what is collected or who it goes to will be
        emailed to account holders before it takes effect, rather than quietly
        edited in. The current version is always the one on this page.
      </P>
    ),
  },
  {
    id: "contact",
    title: "Contact",
    body: (
      <>
        <P>
          Questions, requests and complaints all go to the same place, which is
          a person rather than a ticket queue:
        </P>
        <P>
          <a
            href={`mailto:${CONTACT_EMAIL}`}
            className="font-extrabold underline"
          >
            {CONTACT_EMAIL}
          </a>
        </P>
        <P>In effect {EFFECTIVE}.</P>
      </>
    ),
  },
];

export const PRIVACY_SUMMARY = (
  <>
    <p className="mb-2">
      Your resume is read on our own server by ordinary code, scored
      against public job listings, and the text is kept so your next run works too. The file itself is deleted within minutes.
    </p>
    <p className="mb-2">
      It is <strong>never sold</strong>, never shown to employers or
      recruiters, and <strong>never sent to an AI service or used to
      train a model</strong>.
    </p>
    <p>
      One cookie, and all it does is keep you signed in. No analytics,
      no ad trackers. Replace your resume whenever you like, and one
      email deletes the whole account.
    </p>
  </>
);
