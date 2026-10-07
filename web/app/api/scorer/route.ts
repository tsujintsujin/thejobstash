import { NextResponse } from "next/server";
import { scorerUp } from "@/lib/py";

/** Whether resumes can be taken right now. Read by ScorerNotice. */
export async function GET() {
  return NextResponse.json(
    { up: await scorerUp() },
    { headers: { "Cache-Control": "no-store" } }
  );
}
