import { NextRequest, NextResponse } from "next/server";
import { destroySession } from "@/lib/session";

export async function POST(req: NextRequest) {
  await destroySession();
  // Posted from a plain <form> in the header, so redirect rather than JSON.
  // The origin comes from the request, not from an env var: APP_URL was never
  // set in production, so the fallback sent every sign-out to localhost:3200.
  return NextResponse.redirect(new URL("/", req.url));
}
