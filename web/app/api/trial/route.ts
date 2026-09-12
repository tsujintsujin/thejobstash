import { NextRequest, NextResponse } from "next/server";
import { db, newId, nowIso } from "@/lib/db";
import { pyFile } from "@/lib/py";

/**
 * The free trial. No account, no session, no rows written for the visitor.
 *
 * The important property is that the withheld jobs are withheld HERE. The
 * response carries one real job and a list of bar widths; it never contains
 * the titles, companies, URLs or scores of the locked ones. Blurring them in
 * CSS would be undone by anyone who opens devtools or reads the network tab,
 * so the paywall has to live on this side of the wire.
 */
const MAX_BYTES = 8 * 1024 * 1024;
const ALLOWED = [".pdf", ".docx", ".txt", ".md"];
const LIMIT_PER_HOUR = 4;

/** node:path is gone, and this is all it was used for. */
function extOf(name: string) {
  const dot = name.lastIndexOf(".");
  return dot < 0 ? "" : name.slice(dot).toLowerCase();
}

function callerOf(req: NextRequest) {
  const fwd = req.headers.get("x-forwarded-for");
  if (fwd) return fwd.split(",")[0].trim();
  return req.headers.get("x-real-ip") || "unknown";
}

export async function POST(req: NextRequest) {
  const caller = callerOf(req);

  const recent = await db()
    .prepare(
      "SELECT COUNT(*) c FROM trial_runs WHERE caller=? " +
        "AND created_at >= datetime('now','-1 hour')"
    )
    .bind(caller)
    .first<any>();
  if (recent && recent.c >= LIMIT_PER_HOUR) {
    return NextResponse.json(
      {
        error:
          "That's a few free scans in a row. Try again in an hour, or start a plan for the full list.",
      },
      { status: 429 }
    );
  }

  const form = await req.formData().catch(() => null);
  const file = form?.get("resume") as File | null;
  if (!file) return NextResponse.json({ error: "No file received." }, { status: 400 });

  const ext = extOf(file.name);
  if (!ALLOWED.includes(ext)) {
    return NextResponse.json(
      { error: `We can read ${ALLOWED.join(", ")} files.` },
      { status: 400 }
    );
  }
  if (file.size > MAX_BYTES) {
    return NextResponse.json({ error: "That file is over 8MB." }, { status: 400 });
  }

  try {
    const res = await pyFile("trial", file);

    if (!res.ok) {
      return NextResponse.json(
        { error: res.error || "Couldn't read that resume.", thin: !!res.thin },
        { status: 422 }
      );
    }

    // Logged for rate limiting only. The resume itself is never stored for an
    // anonymous visitor - the bytes are forwarded to the scorer, which writes
    // them to its own temp dir and deletes them in a finally block.
    await db()
      .prepare(
        "INSERT INTO trial_runs (id,caller,matches,created_at) VALUES (?,?,?,?)"
      )
      .bind(newId("trl_"), caller, res.summary?.matches ?? 0, nowIso())
      .run();

    return NextResponse.json(res);
  } catch (e: any) {
    return NextResponse.json(
      { error: `Scan failed: ${e?.message || e}` },
      { status: 500 }
    );
  }
}
