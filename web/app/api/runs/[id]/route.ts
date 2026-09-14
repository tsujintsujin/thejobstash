import { NextRequest, NextResponse } from "next/server";
import { currentUser } from "@/lib/session";
import { failRun, runFor } from "@/lib/db";

/**
 * Where a run is up to. The dashboard polls this after /api/deliver starts a
 * run, because a stale pool means sweeping every board first - longer than
 * Cloudflare holds a request open.
 */

// Well past the slowest sweep seen (JobStreet's full-ad backfill). A run still
// open after this died somewhere nothing could report it - n8n stopped, the
// machine slept - so it is closed here and its credit returned.
const STALE_MS = 45 * 60 * 1000;
const STALE_ERROR = "The run never finished, so your credit has been returned.";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const user = await currentUser();
  if (!user) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const { id } = await params;
  const r = await runFor(user.id, id);
  if (!r) return NextResponse.json({ error: "No such run." }, { status: 404 });

  const open = r.status === "queued" || r.status === "running";
  if (open && Date.now() - Date.parse(r.created_at) > STALE_MS) {
    await failRun(r.id, STALE_ERROR);
    return NextResponse.json({ status: "failed", error: STALE_ERROR });
  }

  return NextResponse.json(
    {
      status: r.status,
      error: r.error,
      delivery_id: r.delivery_id,
      matches: r.matches ?? 0,
      near_misses: r.near_misses ?? 0,
      pdf: !!r.pdf_path,
    },
    { headers: { "Cache-Control": "no-store" } }
  );
}
