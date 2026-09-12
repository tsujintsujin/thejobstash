import { NextResponse } from "next/server";
import { destroySession } from "@/lib/session";

export async function POST() {
  await destroySession();
  // Posted from a plain <form> in the header, so redirect rather than JSON.
  return NextResponse.redirect(
    new URL("/", process.env.APP_URL || "http://localhost:3200")
  );
}
