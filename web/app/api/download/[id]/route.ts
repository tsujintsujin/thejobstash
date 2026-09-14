import { NextRequest, NextResponse } from "next/server";
import { currentUser } from "@/lib/session";
import { db } from "@/lib/db";
import { env } from "@/lib/cf";
import { pyGetFile } from "@/lib/py";

// A signed-in user's own digest: never cacheable, and the stale-410 this
// route served for hours is what a cached error response looks like.
export const dynamic = "force-dynamic";
export const revalidate = 0;

// A digest is HTML built from text scraped off job boards and served from
// this origin, next to the session cookie. render.py escapes every field, and
// this is the second lock: the page may not run any script at all, so an
// escaping bug or a hostile posting still cannot act as the signed-in user.
const DIGEST_CSP =
  "sandbox allow-popups allow-popups-to-escape-sandbox " +
  "allow-top-navigation-by-user-activation; default-src 'none'; " +
  "style-src 'unsafe-inline'; img-src data: https:; font-src data:";

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
  if (!user) return new NextResponse("Sign in first.", { status: 401, headers: { "Cache-Control": "private, no-store" } });

  const { id } = await ctx.params;
  const row = await db()
    .prepare("SELECT html_path,pdf_path,day FROM deliveries WHERE id=? AND user_id=?")
    .bind(id, user.id)
    .first<any>();
  if (!row) return new NextResponse("Not found.", { status: 404, headers: { "Cache-Control": "private, no-store" } });

  const wantPdf = req.nextUrl.searchParams.get("format") !== "html";
  const target: string | null = wantPdf ? row.pdf_path : row.html_path;
  if (!target) return new NextResponse("That format wasn't generated.", { status: 404, headers: { "Cache-Control": "private, no-store" } });

  // Anything that is not an R2 key is a path on the machine that rendered it.
  // That machine is already reachable over the tunnel that carries the
  // scorer, so fetch the file from there instead of telling the user their
  // digest does not exist. R2 was never enabled, so before this EVERY View and
  // PDF button on the dashboard answered 410 for every digest ever produced.
  //
  // Only the basename is sent. The row was already matched on user_id, so the
  // caller owns this delivery; py_server refuses anything outside outbox/.
  if (!target.startsWith("r2:")) {
    const name = target.replace(/\\/g, "/").split("/").pop() || "";
    const file = await pyGetFile(
      `/digest?name=${encodeURIComponent(name)}`,
      wantPdf ? "application/pdf" : "text/html"
    );
    if (!file) {
      return new NextResponse(
        "The machine that rendered this digest is offline. The copy emailed " +
          "to you is unaffected.",
        { status: 503, headers: { "Cache-Control": "private, no-store" } }
      );
    }
    return new NextResponse(file, {
      headers: {
        "Content-Type": wantPdf
          ? "application/pdf"
          : "text/html; charset=utf-8",
        "Content-Disposition":
          `${wantPdf ? "attachment" : "inline"}; ` +
          `filename="jobstash-${row.day}.${wantPdf ? "pdf" : "html"}"`,
        "Cache-Control": "private, no-store",
        ...(wantPdf ? {} : { "Content-Security-Policy": DIGEST_CSP }),
      },
    });
  }

  const key = target.slice(3);
  if (!key.startsWith(`${user.id}/`)) {
    return new NextResponse("Refused.", { status: 403, headers: { "Cache-Control": "private, no-store" } });
  }

  // R2 is not subscribed yet, so the bucket binding can be absent entirely.
  // The emailed PDF is the delivered artefact either way; this button is the
  // convenience copy, so it says so plainly rather than throwing.
  const bucket = env().DIGESTS;
  if (!bucket) {
    return new NextResponse("Digest storage isn't switched on yet.", { status: 503, headers: { "Cache-Control": "private, no-store" } });
  }

  const obj = await bucket.get(key);
  if (!obj) return new NextResponse("That file is no longer stored.", { status: 410, headers: { "Cache-Control": "private, no-store" } });

  return new NextResponse(obj.body, {
    headers: {
      "Content-Type": wantPdf ? "application/pdf" : "text/html; charset=utf-8",
      "Content-Disposition":
        `${wantPdf ? "attachment" : "inline"}; ` +
        `filename="jobstash-${row.day}.${wantPdf ? "pdf" : "html"}"`,
      "Cache-Control": "private, no-store",
      ...(wantPdf ? {} : { "Content-Security-Policy": DIGEST_CSP }),
    },
  });
}

/**
 * Remove one digest from the account.
 *
 * Same id-AND-user_id lookup as GET, so an id from another account is a 404
 * rather than a deletion. The R2 object goes with the row when the bucket is
 * bound; the rendered copy in this machine's outbox/ is left alone, and so is
 * the email that was already sent.
 */
export async function DELETE(
  _req: NextRequest,
  ctx: { params: Promise<{ id: string }> }
) {
  const user = await currentUser();
  if (!user) return new NextResponse("Sign in first.", { status: 401, headers: { "Cache-Control": "private, no-store" } });

  const { id } = await ctx.params;
  const row = await db()
    .prepare("SELECT html_path,pdf_path FROM deliveries WHERE id=? AND user_id=?")
    .bind(id, user.id)
    .first<any>();
  if (!row) return new NextResponse("Not found.", { status: 404, headers: { "Cache-Control": "private, no-store" } });

  const bucket = env().DIGESTS;
  if (bucket) {
    for (const p of [row.html_path, row.pdf_path] as (string | null)[]) {
      if (p?.startsWith("r2:") && p.slice(3).startsWith(`${user.id}/`)) {
        await bucket.delete(p.slice(3));
      }
    }
  }

  await db().prepare("DELETE FROM deliveries WHERE id=? AND user_id=?").bind(id, user.id).run();
  return new NextResponse(null, { status: 204, headers: { "Cache-Control": "private, no-store" } });
}
