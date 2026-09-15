"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * The signed-out nav CTAs point at the auth card - so on the auth card itself
 * they are two buttons that go where you already are, sitting directly above
 * a control offering the same two choices. Hidden there; the logo still gets
 * you home.
 */
const HIDE_CTAS_ON = ["/signup", "/login"];

const ROW = "flex items-center gap-2.5 max-[560px]:gap-[7px]";

export default function NavLinks({ signedIn }: { signedIn: boolean }) {
  const pathname = usePathname();

  if (signedIn) {
    return (
      <div className={ROW}>
        {pathname !== "/dashboard" && (
          <Link href="/dashboard" className="btn btn-paper btn-sm">
            Dashboard
          </Link>
        )}
        <form action="/api/auth/logout" method="post">
          <button className="btn btn-sm" type="submit">
            Sign out
          </button>
        </form>
      </div>
    );
  }

  if (HIDE_CTAS_ON.some((p) => pathname === p || pathname.startsWith(p + "/"))) {
    return <div className={ROW} />;
  }

  return (
    <div className={ROW}>
      <Link href="/signup?mode=signin" className="btn btn-paper btn-sm">
        Sign in
      </Link>
      <Link href="/signup" className="btn btn-sm">
        Get started
      </Link>
    </div>
  );
}
