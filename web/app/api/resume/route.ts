import { NextRequest, NextResponse } from "next/server";
import { currentUser } from "@/lib/session";
import { saveProfile, profileFor, db } from "@/lib/db";
import { workSetupFlags, workSetupOf } from "@/lib/workSetup";
import { pyFile } from "@/lib/py";

const MAX_BYTES = 8 * 1024 * 1024;
const ALLOWED = [".pdf", ".docx", ".txt", ".md"];

/** node:path is gone, and this is all it was used for. */
function extOf(name: string) {
  const dot = name.lastIndexOf(".");
  return dot < 0 ? "" : name.slice(dot).toLowerCase();
}

export async function POST(req: NextRequest) {
  const user = await currentUser();
  if (!user) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const form = await req.formData().catch(() => null);
  const file = form?.get("resume") as File | null;
  if (!file) return NextResponse.json({ error: "No file received." }, { status: 400 });

  const ext = extOf(file.name);
  if (!ALLOWED.includes(ext)) {
    return NextResponse.json(
      { error: `We can read ${ALLOWED.join(", ")} files.` },
      { status: 400 }
    );
  }
  if (file.size > MAX_BYTES) {
    return NextResponse.json({ error: "That file is over 8MB." }, { status: 400 });
  }

  // The bytes are forwarded to the scorer and forgotten. There is no disk on
  // a Worker to write a temp file to, and no reason to want one: the parsed
  // text is what we keep, the original file is not retained on either side.
  try {
    const res = await pyFile("parse", file);

    if (!res.ok) {
      return NextResponse.json(
        { error: res.error || "Couldn't read that resume.", thin: !!res.thin },
        { status: 422 }
      );
    }

    // A resume rarely states remote/hybrid/onsite, so a fresh parse must not
    // reset what the user picked on the dashboard.
    const prev = await profileFor(user.id);
    const kept = prev ? workSetupFlags(workSetupOf(JSON.parse(prev.profile_json))) : {};
    const profile = { ...res.profile, ...kept, user_id: user.id };
    await saveProfile(user.id, file.name, res.resume_text || "", JSON.stringify(profile));

    return NextResponse.json({
      ok: true,
      diagnostics: res.diagnostics,
      profile,
    });
  } catch (e: any) {
    return NextResponse.json(
      { error: `Upload failed: ${e?.message || e}` },
      { status: 500 }
    );
  }
}

export async function DELETE() {
  const user = await currentUser();
  if (!user) return NextResponse.json({ error: "Sign in first." }, { status: 401 });
  await db().prepare("DELETE FROM profiles WHERE user_id=?").bind(user.id).run();
  return NextResponse.json({ ok: true });
}
