import { NextRequest, NextResponse } from "next/server";
import { currentUser } from "@/lib/session";
import { profileFor, saveProfileJson } from "@/lib/db";
import { MAX_YEARS, levelFromYears } from "@/lib/experience";

/** Set years of experience; seniority follows. See lib/experience.ts. */
export async function POST(req: NextRequest) {
  const user = await currentUser();
  if (!user) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const body = (await req.json().catch(() => ({}))) as { years?: unknown };
  const years = body.years;
  if (typeof years !== "number" || !Number.isInteger(years) || years < 0 || years > MAX_YEARS) {
    return NextResponse.json({ error: "Years must be 0 to 50." }, { status: 400 });
  }

  const row = await profileFor(user.id);
  if (!row) return NextResponse.json({ error: "No resume yet." }, { status: 404 });

  const level = levelFromYears(years);
  const profile = { ...JSON.parse(row.profile_json), years_experience: years, level };
  await saveProfileJson(user.id, JSON.stringify(profile));
  return NextResponse.json({ ok: true, years, level });
}
