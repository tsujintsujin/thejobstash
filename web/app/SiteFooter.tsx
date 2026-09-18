"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CONTACT_EMAIL } from "@/app/legal/shell";

/**
 * The footer belongs on every page - a page that just ends is what made the
 * dark block float mid-screen in the first place.
 *
 * The auth pages get a one-line version of the same content rather than a
 * missing one. Measured: the full footer is 221px, and the auth card needs
 * that space to fit a screen without scrolling.
 */
const SLIM_ON = ["/signup", "/login"];

/* mt-auto is the other half of the sticky footer; see the note on body. */
const SHELL = "bg-ink text-bone mt-auto";
const LINK = "text-sm opacity-80 no-underline hover:opacity-100 hover:underline";
const SUPPORT = `mailto:${CONTACT_EMAIL}`;
const COPYRIGHT = "© 2026 TheJobStash. All rights reserved.";

/* Simple Icons paths, 24x24. Greyed out until the accounts exist. */
const SOCIALS = [
  {
    name: "X",
    d: "M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.638 7.584H.474l8.6-9.83L0 1.154h7.594l5.243 6.932ZM17.61 20.644h2.039L6.486 3.24H4.298Z",
  },
  {
    name: "GitHub",
    d: "M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12",
  },
  {
    name: "LinkedIn",
    d: "M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.878 1.637-1.8 3.37-1.8 3.601 0 4.267 2.37 4.267 4.892v6.249zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z",
  },
];

function Brand({ size }: { size: string }) {
  return (
    <div className="flex items-baseline gap-2 flex-wrap">
      <span className={`${size} font-extrabold tracking-[-0.03em]`}>
        TheJobStash
      </span>
      <span className="text-[10px] font-bold uppercase tracking-[0.1em] opacity-60">
        by TSUJIN IT SOLUTIONS
      </span>
    </div>
  );
}

export default function SiteFooter() {
  const pathname = usePathname();
  const slim = SLIM_ON.some((p) => pathname === p || pathname.startsWith(p + "/"));

  if (slim) {
    return (
      <footer className={`${SHELL} py-4 sq1:py-2 sq3:py-1.5 sq4:py-1`}>
        <div className="wrap flex items-center justify-between gap-3.5 flex-wrap">
          <Brand size="text-[17px]" />
          <nav className="flex gap-4 gap-y-1 text-xs font-bold flex-wrap">
            <Link href="/how-it-works" className={LINK}>How it works</Link>
            <Link href="/#pricing" className={LINK}>Pricing</Link>
            <Link href="/#faq" className={LINK}>FAQ</Link>
            {/* The slim footer is the ONLY footer on /signup and /login, so
                the legal links have to survive the trim: this is the one page
                where somebody is about to hand over an email and a resume. */}
            <Link href="/privacy" className={LINK}>Privacy</Link>
            <Link href="/terms" className={LINK}>Terms</Link>
            <a href={SUPPORT} className={LINK}>Support</a>
          </nav>
          <p className="text-[11px] opacity-55">{COPYRIGHT}</p>
        </div>
      </footer>
    );
  }

  return (
    <footer className={`${SHELL} pt-[46px] pb-[30px]`}>
      <div className="wrap">
        <div className="flex justify-between gap-6 flex-wrap">
          <div>
            <Brand size="text-[27px]" />
            <p className="text-[13px] opacity-70 mt-2">
              Thirteen job boards, one resume, no noise.
            </p>
            <p className="text-[13px] opacity-70 mt-1">
              Have a suggestion? Send us an email at{" "}
              <a href={SUPPORT} className="font-bold underline hover:opacity-100">
                {CONTACT_EMAIL}
              </a>
            </p>
            <div className="flex gap-3 mt-4">
              {SOCIALS.map((s) => (
                /* Not links: there is nowhere to go yet. Focusable so the
                   tooltip reaches keyboard users too. */
                <span
                  key={s.name}
                  tabIndex={0}
                  role="img"
                  aria-label={`${s.name} — coming soon`}
                  className="group relative cursor-not-allowed outline-none"
                >
                  {/* Opacity on the icon, not the wrapper, or the tooltip greys out too. */}
                  <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden className="opacity-35">
                    <path d={s.d} />
                  </svg>
                  <span
                    className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2
                               whitespace-nowrap bg-bone text-ink text-[11px] font-bold px-2 py-1
                               opacity-0 group-hover:opacity-100 group-focus:opacity-100"
                  >
                    Coming soon!
                  </span>
                </span>
              ))}
            </div>
          </div>
          <div className="flex gap-[30px] flex-wrap">
            <div className="grid gap-[7px] content-start">
              <Link href="/signup" className={LINK}>Get started</Link>
              <Link href="/signup?mode=signin" className={LINK}>Sign in</Link>
              <a href={SUPPORT} className={LINK}>Support</a>
            </div>
            <div className="grid gap-[7px] content-start">
              <Link href="/how-it-works" className={LINK}>How it works</Link>
              <Link href="/jobs" className={LINK}>Jobs by role</Link>
              <Link href="/#pricing" className={LINK}>Pricing</Link>
              <Link href="/#faq" className={LINK}>FAQ</Link>
              <Link href="/about" className={LINK}>About</Link>
            </div>
            <div className="grid gap-[7px] content-start">
              <Link href="/privacy" className={LINK}>Privacy</Link>
              <Link href="/terms" className={LINK}>Terms</Link>
              <Link href="/refunds" className={LINK}>Refunds</Link>
            </div>
          </div>
        </div>
        {/* Bone at low alpha, not a grey line: the rule tints with the ink
            beneath it instead of laying a foreign neutral over it. */}
        <div className="flex justify-between gap-x-6 gap-y-2 flex-wrap text-[11px] opacity-50
                        mt-[34px] pt-4 border-t border-bone-line">
          <p>
            Credits are bought per run through PayMongo — no subscription,
            nothing recurring.
          </p>
          <p>{COPYRIGHT}</p>
        </div>
      </div>
    </footer>
  );
}
