"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

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

export default function SiteFooter() {
  const pathname = usePathname();
  const slim = SLIM_ON.some((p) => pathname === p || pathname.startsWith(p + "/"));

  if (slim) {
    return (
      <footer className={`${SHELL} py-4 sq1:py-2 sq3:py-1.5 sq4:py-1`}>
        <div className="wrap flex items-center justify-between gap-3.5 flex-wrap">
          <span className="text-[15px] font-extrabold tracking-[-0.03em]">
            TheJobStash
          </span>
          <nav className="flex gap-4 text-xs font-bold">
            <Link href="/#how" className={LINK}>How it works</Link>
            <Link href="/#plans" className={LINK}>Plans</Link>
            <Link href="/#faq" className={LINK}>FAQ</Link>
            {/* The slim footer is the ONLY footer on /signup and /login, so
                the legal links have to survive the trim: this is the one page
                where somebody is about to hand over an email and a resume. */}
            <Link href="/privacy" className={LINK}>Privacy</Link>
            <Link href="/terms" className={LINK}>Terms</Link>
          </nav>
          <p className="text-[11px] opacity-55">
            Payments are off while the product is in testing.
          </p>
        </div>
      </footer>
    );
  }

  return (
    <footer className={`${SHELL} pt-[46px] pb-[30px]`}>
      <div className="wrap">
        <div className="flex justify-between gap-6 flex-wrap">
          <div>
            <div className="text-[22px] font-extrabold tracking-[-0.03em]">
              TheJobStash
            </div>
            <p className="text-[13px] opacity-70 mt-2">
              Ten job boards, one resume, no noise.
            </p>
          </div>
          <div className="flex gap-[30px] flex-wrap">
            <div className="grid gap-[7px]">
              <Link href="/signup" className={LINK}>Get started</Link>
              <Link href="/signup?mode=signin" className={LINK}>Sign in</Link>
              <Link href="/dashboard" className={LINK}>Dashboard</Link>
            </div>
            <div className="grid gap-[7px]">
              <Link href="/#how" className={LINK}>How it works</Link>
              <Link href="/#plans" className={LINK}>Plans</Link>
              <Link href="/#faq" className={LINK}>FAQ</Link>
            </div>
            <div className="grid gap-[7px]">
              <Link href="/privacy" className={LINK}>Privacy</Link>
              <Link href="/terms" className={LINK}>Terms</Link>
            </div>
          </div>
        </div>
        {/* Bone at low alpha, not a grey line: the rule tints with the ink
            beneath it instead of laying a foreign neutral over it. */}
        <p className="text-[11px] opacity-50 mt-[34px] pt-4 border-t border-bone-line">
          Payments are switched off while the product is in testing — plans are
          granted free.
        </p>
      </div>
    </footer>
  );
}
