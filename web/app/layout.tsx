import type { Metadata } from "next";
import Link from "next/link";
import { currentUser } from "@/lib/session";
import NavLinks from "./NavLinks";
import SiteFooter from "./SiteFooter";
import "./globals.css";

export const metadata: Metadata = {
  title: "TheJobStash — jobs that actually match your resume",
  description:
    "Upload a resume once. Every morning we score thousands of live postings " +
    "against it and email you the handful worth your time — plus the ones " +
    "that came close, and exactly why they didn't.",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await currentUser();

  return (
    <html lang="en">
      <body>
        {/* Bone, not paper: the nav sits on the page ground and is separated
            from it by the border, not by a change of colour. */}
        <nav className="border-b-3 border-ink bg-bone sticky top-0 z-50">
          <div className="wrap flex items-center justify-between gap-4 h-[68px]
                          max-[560px]:h-auto max-[560px]:py-[11px]
                          max-[560px]:gap-2">
            <Link
              href="/"
              className="text-[21px] font-extrabold tracking-[-0.03em]
                         no-underline max-[560px]:text-[17px]"
            >
              TheJobStash
            </Link>
            <NavLinks signedIn={!!user} />
          </div>
        </nav>

        {children}

        <SiteFooter />
      </body>
    </html>
  );
}
