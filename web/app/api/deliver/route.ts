import { NextResponse } from "next/server";
import { currentUser } from "@/lib/session";
import { failRun, openRunFor, profileFor, startRun } from "@/lib/db";
import { pyRun } from "@/lib/py";

/**
 * Start one run of this account's resume. Costs one credit.
 *
 * The credit is taken here, before anything runs, so two clicks cannot spend
 * one credit twice. The run itself - score the pool, render - happens in n8n
 * on the scorer machine (it never scrapes; the cleanup workflow does) and can
 * take longer than Cloudflare holds a request open. So this answers with a run
 * id at once, and the dashboard polls /api/runs/<id>.
 *
 * If the scorer machine or n8n cannot take the run, the credit goes straight
 * back. Nothing in the digest itself is withheld: a run produces the whole
 * stash, unlocked.
 */
export async function POST() {
  const user = await currentUser();
  if (!user) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  if (!(await profileFor(user.id))) {
    return NextResponse.json(
      { error: "Upload a resume first — there's nothing to score against." },
      { status: 400 }
    );
  }

  const runId = await startRun(user.id);
  if (!runId) {
    if (await openRunFor(user.id)) {
      return NextResponse.json(
        { error: "Your resume is already running. It lands under Past digests when it finishes." },
        { status: 409 }
      );
    }
    return NextResponse.json(
      { error: "You're out of credits. Buy a pack to run your resume again." },
      { status: 402 }
    );
  }

  const res = await pyRun(user.id, runId);
  if (!res.ok) {
    const why = res.error || "The scorer is offline.";
    await failRun(runId, why);
    return NextResponse.json(
      { error: `${why} Your credit has been returned.` },
      { status: 503 }
    );
  }
  return NextResponse.json({ ok: true, run_id: runId });
}
