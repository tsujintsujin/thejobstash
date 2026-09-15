import { NextRequest, NextResponse } from "next/server";
import { env, envVar } from "@/lib/cf";

/**
 * Where the machine that renders digests puts them.
 *
 * Not reachable by a browser in any meaningful sense: it takes the same shared
 * secret the Worker uses to call the scorer, and that secret only exists on
 * the two ends. Uploading through here rather than straight to R2 means the
 * renderer needs no S3 credentials and no request signing - the bucket is
 * already a binding on this side.
 */
const MAX_BYTES = 16 * 1024 * 1024;

/** Keys are `<user_id>/<delivery_id>.<ext>` and nothing else is accepted. */
const KEY = /^usr_[0-9a-f]{16}\/dlv_[0-9a-f]{16}\.(html|pdf)$/;

function authorised(req: NextRequest) {
  const expected = envVar("JOBSTASH_PY_TOKEN");
  if (!expected) return false;
  const got = (req.headers.get("authorization") || "").replace(/^Bearer /, "");
  if (got.length !== expected.length) return false;
  // Constant-time: `===` on a secret leaks its prefix through timing.
  let diff = 0;
  for (let i = 0; i < got.length; i++) diff |= got.charCodeAt(i) ^ expected.charCodeAt(i);
  return diff === 0;
}

export async function PUT(req: NextRequest) {
  if (!authorised(req)) {
    return NextResponse.json({ error: "unauthorised" }, { status: 401 });
  }

  const key = req.nextUrl.searchParams.get("key") || "";
  if (!KEY.test(key)) {
    return NextResponse.json({ error: "bad key" }, { status: 400 });
  }

  const length = Number(req.headers.get("content-length") || 0);
  if (!length || length > MAX_BYTES) {
    return NextResponse.json({ error: "bad length" }, { status: 413 });
  }

  const body = await req.arrayBuffer();
  if (body.byteLength > MAX_BYTES) {
    return NextResponse.json({ error: "too large" }, { status: 413 });
  }

  const bucket = env().DIGESTS;
  if (!bucket) {
    // Told plainly so r2.py logs a real reason and keeps the local path,
    // rather than recording a key for an object that was never stored.
    return NextResponse.json({ error: "R2 is not enabled" }, { status: 503 });
  }

  await bucket.put(key, body, {
    httpMetadata: {
      contentType:
        req.headers.get("content-type") ||
        (key.endsWith(".pdf") ? "application/pdf" : "text/html; charset=utf-8"),
    },
  });

  return NextResponse.json({ ok: true, key });
}
