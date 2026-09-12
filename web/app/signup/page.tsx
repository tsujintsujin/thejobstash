import { redirect } from "next/navigation";
import { currentUser, safeNext } from "@/lib/session";
import { googleConfigured } from "@/lib/google";
import { poolStats } from "@/lib/db";
import AuthCard from "./AuthCard";

export const dynamic = "force-dynamic";

export default async function Auth({
  searchParams,
}: {
  searchParams: Promise<{ mode?: string; next?: string; err?: string }>;
}) {
  const sp = await searchParams;
  const next = safeNext(sp.next);

  // Already signed in? Neither face of this card is the page they wanted.
  if (await currentUser()) redirect(next);

  // Real numbers on the panel. One aggregate query against D1, and a made-up
  // figure on a signup page is the kind of thing that stops being harmless
  // the moment somebody checks it.
  const { pool, sources } = await poolStats();

  // Jade, not the action colour: this page IS the action, so the ground
  // stays positive and flare is left free for the button that ends it.
  return (
    <main className="band band-solo bg-jade">
      <div className="max-w-auth mx-auto px-6">
        <AuthCard
          initialMode={sp.mode === "signin" ? "signin" : "create"}
          next={next}
          googleReady={googleConfigured()}
          initialError={typeof sp.err === "string" ? sp.err.slice(0, 200) : ""}
          pool={pool}
          sources={sources}
        />

      </div>
    </main>
  );
}
