import { NextRequest, NextResponse } from "next/server";
import { currentUser, } from "@/lib/session";
import { activeEntitlement, profileFor } from "@/lib/db";
import { pyUser } from "@/lib/py";

/**
 * Generate today's digest on demand.
 *
 * ?preview=1 scores without consuming anything, so the dashboard can show the
 * list without burning the jobs it displays. Without it, this is the real
 * thing: it writes sent_jobs, records a delivery and posts the email.
 */
export async function POST(req: NextRequest) {
  const user = await currentUser();
  if (!user) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  if (!(await profileFor(user.id))) {
    return NextResponse.json(
      { error: "Upload a resume first — there's nothing to score against." },
      { status: 400 }
    );
  }

  const preview = req.nextUrl.searchParams.get("preview") === "1";
  if (!preview && !(await activeEntitlement(user.id))) {
    return NextResponse.json(
      { error: "Your plan has run out. Start another to keep getting digests." },
      { status: 402 }
    );
  }

  const res = await pyUser(preview ? "preview" : "deliver", user.id);
  if (!res.ok) {
    return NextResponse.json(
      { error: res.error || "Scoring failed." },
      { status: 500 }
    );
  }
  return NextResponse.json(res);
}
