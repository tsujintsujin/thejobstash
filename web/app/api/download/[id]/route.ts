import { NextRequest, NextResponse } from "next/server";
import { currentUser } from "@/lib/session";
import { db } from "@/lib/db";
import { env } from "@/lib/cf";

/**
 * Serve a rendered digest out of R2.
 *
 * The row is looked up by id AND user_id, so one account cannot read
 * another's file by guessing an id. The stored value is still never trusted
 * as a path: only an `r2:` key is followed, and it is confirmed to sit under
 * that user's own prefix before the object is fetched. The Worker has no
 * filesystem, so the traversal class of bug this used to guard against is
 * gone - but the prefix check is what keeps one user's key from naming
 * another user's object.
 */
export async function GET(
  req: NextRequest,
  ctx: { params: Promise<{ id: string }> }
) {
  const user = await currentUser();
  if (!user) return new NextResponse("Sign in first.", { status: 401 });

  const { id } = await ctx.params;
  const row = await db()
    .prepare("SELECT html_path,pdf_path,day FROM deliveries WHERE id=? AND user_id=?")
    .bind(id, user.id)
    .first<any>();
  if (!row) return new NextResponse("Not found.", { status: 404 });

  const wantPdf = req.nextUrl.searchParams.get("format") !== "html";
  const target: string | null = wantPdf ? row.pdf_path : row.html_path;
  if (!target) return new NextResponse("That format wasn't generated.", { status: 404 });

  // Anything that is not an R2 key is a path on the machine that rendered it,
  // which this Worker cannot reach. Say so rather than 500.
  if (!target.startsWith("r2:")) {
    return new NextResponse("That file was never uploaded.", { status: 410 });
  }

  const key = target.slice(3);
  if (!key.startsWith(`${user.id}/`)) {
    return new NextResponse("Refused.", { status: 403 });
  }

  // R2 is not subscribed yet, so the bucket binding can be absent entirely.
  // The emailed PDF is the delivered artefact either way; this button is the
  // convenience copy, so it says so plainly rather than throwing.
  const bucket = env().DIGESTS;
  if (!bucket) {
    return new NextResponse("Digest storage isn't switched on yet.", { status: 503 });
  }

  const obj = await bucket.get(key);
  if (!obj) return new NextResponse("That file is no longer stored.", { status: 410 });

  return new NextResponse(obj.body, {
    headers: {
      "Content-Type": wantPdf ? "application/pdf" : "text/html; charset=utf-8",
      "Content-Disposition":
        `${wantPdf ? "attachment" : "inline"}; ` +
        `filename="jobstash-${row.day}.${wantPdf ? "pdf" : "html"}"`,
    },
  });
}
