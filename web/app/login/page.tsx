import { redirect } from "next/navigation";
import { safeNext } from "@/lib/session";

/**
 * /login is no longer a page - signing in and signing up are two faces of one
 * card at /signup. This stays as a redirect rather than being deleted because
 * the address is in the wild: bookmarks, a seeded demo account handed round,
 * and every earlier build's nav. A 404 for someone trying to sign in is a
 * worse outcome than one extra hop.
 */
export default async function LoginRedirect({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const next = safeNext((await searchParams).next);
  redirect(
    next === "/dashboard"
      ? "/signup?mode=signin"
      : `/signup?mode=signin&next=${encodeURIComponent(next)}`
  );
}
