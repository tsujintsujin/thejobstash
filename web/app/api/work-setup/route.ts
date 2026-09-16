import { NextRequest, NextResponse } from "next/server";
import { currentUser } from "@/lib/session";
import { profileFor, saveProfileJson } from "@/lib/db";
import { WORK_SETUPS, WorkSetup, workSetupFlags } from "@/lib/workSetup";

/** Set remote / hybrid / onsite for scoring. See lib/workSetup.ts. */
export async function POST(req: NextRequest) {
  const user = await currentUser();
  if (!user) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const body = (await req.json().catch(() => ({}))) as { setup?: unknown };
  const setup = body.setup as WorkSetup;
  if (!WORK_SETUPS.includes(setup)) {
    return NextResponse.json({ error: "Unknown work setup." }, { status: 400 });
  }

  const row = await profileFor(user.id);
  if (!row) return NextResponse.json({ error: "No resume yet." }, { status: 404 });

  const profile = { ...JSON.parse(row.profile_json), ...workSetupFlags(setup) };
  await saveProfileJson(user.id, JSON.stringify(profile));
  return NextResponse.json({ ok: true, setup });
}
