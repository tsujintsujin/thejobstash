import type { Metadata } from "next";
import Link from "next/link";
import { currentUser } from "@/lib/session";
import NavLinks from "./NavLinks";
import SiteFooter from "./SiteFooter";
import { SITE_DESCRIPTION, SITE_NAME, SITE_TAGLINE, SITE_URL } from "@/lib/site";
import "./globals.css";

/* Defaults every page inherits. A page sets its own `title` (the template adds
   the brand) and its own `alternates.canonical` via pageMeta(); the image comes from
   app/opengraph-image.png, which Next attaches automatically. */
export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: `${SITE_NAME} — ${SITE_TAGLINE.toLowerCase()}`,
    template: `%s — ${SITE_NAME}`,
  },
  description: SITE_DESCRIPTION,
  applicationName: SITE_NAME,
  // No canonical here: a child page that forgot its own would inherit this
  // one and tell Google it is a duplicate of the home page.
  openGraph: {
    type: "website",
    siteName: SITE_NAME,
    locale: "en_PH",
    title: `${SITE_NAME} — ${SITE_TAGLINE}`,
    description: SITE_DESCRIPTION,
  },
  twitter: {
    card: "summary_large_image",
    title: `${SITE_NAME} — ${SITE_TAGLINE}`,
    description: SITE_DESCRIPTION,
  },
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
