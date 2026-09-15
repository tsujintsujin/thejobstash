import { NextRequest, NextResponse } from "next/server";
import { currentUser } from "@/lib/session";
import { profileFor, saveProfileJson } from "@/lib/db";

/**
 * Switch one skill off, or back on, for scoring.
 *
 * The skill stays in strong_skills as stored — that is the list the dashboard
 * shows, and a skill you cannot see is a skill you cannot re-enable. The
 * exclusion lives in disabled_skills, and Profile.__post_init__ on the Python
 * side is the single place that applies it, so the scorer, the near-miss
 * reasons and the family-skill check all agree without any of them knowing
 * this route exists.
 */
export async function POST(req: NextRequest) {
  const user = await currentUser();
  if (!user) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const body = (await req.json().catch(() => ({}))) as {
    skill?: unknown;
    enabled?: unknown;
  };
  const skill = typeof body.skill === "string" ? body.skill.trim() : "";
  if (!skill) return NextResponse.json({ error: "No skill given." }, { status: 400 });
  const enabled = body.enabled !== false;

  const row = await profileFor(user.id);
  if (!row) return NextResponse.json({ error: "No resume yet." }, { status: 404 });

  const profile = JSON.parse(row.profile_json);
  // Only a skill this resume actually claims can be switched off, so the
  // stored list can never fill up with anything the dashboard isn't showing.
  const known = Object.keys(profile.strong_skills || {});
  const match = known.find((s) => s.toLowerCase() === skill.toLowerCase());
  if (!match) return NextResponse.json({ error: "Unknown skill." }, { status: 400 });

  const off = new Set<string>(
    (profile.disabled_skills || []).map((s: string) => s.toLowerCase())
  );
  if (enabled) off.delete(match.toLowerCase());
  else off.add(match.toLowerCase());
  profile.disabled_skills = [...off];

  await saveProfileJson(user.id, JSON.stringify(profile));
  return NextResponse.json({ ok: true, disabled: profile.disabled_skills });
}
