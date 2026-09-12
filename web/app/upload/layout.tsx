import { redirect } from "next/navigation";
import { currentUser } from "@/lib/session";

/**
 * The upload form posts to /api/resume, which requires a session. Without this
 * guard a logged-out visitor read "Step 2 of 2", chose a file and waited for
 * the parse, only to be told "Sign in first." - the check has to happen before
 * the form, not after the work. Sending `next` back means signing in resumes
 * the step they were on instead of dropping them on the dashboard.
 */
export default async function UploadLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await currentUser();
  if (!user) redirect("/signup?mode=signin&next=%2Fupload");
  return <>{children}</>;
}
