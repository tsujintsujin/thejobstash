import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { envVar } from "@/lib/cf";

/**
 * D1, for the machine that runs the scorer.
 *
 * `d1.py` on that machine needs the same database this Worker reads, and the
 * obvious way - Cloudflare's own D1 REST API - means minting an account-scoped
 * API token and leaving it on a home PC, where it could reach every database
 * in the account. This endpoint does the same job with the secret that already
 * exists for the tunnel, and it can only ever touch this one binding.
 *
 * The response is shaped exactly like Cloudflare's D1 API on purpose, so
 * d1.py parses one format whichever way it is pointed.
 *
 * This runs arbitrary SQL. That is the point - it is the same access the
 * Python has always had to jobstash.db - and it is why the bearer check below
 * is the only thing standing in front of it.
 */
const MAX_STATEMENTS = 50;

function authorised(req: NextRequest) {
  const expected = envVar("JOBSTASH_PY_TOKEN");
  if (!expected) return false;
  const got = (req.headers.get("authorization") || "").replace(/^Bearer /, "");
  if (got.length !== expected.length) return false;
  let diff = 0;
  for (let i = 0; i < got.length; i++) diff |= got.charCodeAt(i) ^ expected.charCodeAt(i);
  return diff === 0;
}

type Stmt = { sql?: unknown; params?: unknown };

function prepare(s: Stmt) {
  if (typeof s?.sql !== "string" || !s.sql.trim()) throw new Error("sql required");
  const params = Array.isArray(s.params) ? s.params : [];
  return db().prepare(s.sql).bind(...params);
}

/** Cloudflare's D1 API envelope, which d1.py already knows how to read. */
function envelope(results: any[]) {
  return NextResponse.json({
    success: true,
    errors: [],
    messages: [],
    result: results.map((r) => ({
      results: r?.results ?? [],
      success: true,
      meta: { changes: r?.meta?.changes ?? 0 },
    })),
  });
}

export async function POST(req: NextRequest) {
  if (!authorised(req)) {
    return NextResponse.json(
      { success: false, errors: [{ message: "unauthorised" }] },
      { status: 401 }
    );
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { success: false, errors: [{ message: "bad JSON" }] },
      { status: 400 }
    );
  }

  try {
    // An array is executemany: one round trip carrying many statements.
    if (Array.isArray(body)) {
      if (!body.length || body.length > MAX_STATEMENTS) {
        return NextResponse.json(
          { success: false, errors: [{ message: "1..50 statements" }] },
          { status: 400 }
        );
      }
      const out = await db().batch(body.map((s) => prepare(s as Stmt)));
      return envelope(out as any[]);
    }

    const out = await prepare(body as Stmt).all();
    return envelope([out]);
  } catch (e: any) {
    // The message goes back to the scorer, which logs it. It never reaches a
    // browser, and the caller is already trusted with the SQL that caused it.
    console.error(`[d1] ${e?.message || e}`);
    return NextResponse.json(
      { success: false, errors: [{ message: String(e?.message || e).slice(0, 300) }] },
      { status: 400 }
    );
  }
}
