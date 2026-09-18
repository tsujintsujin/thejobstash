import Link from "next/link";

export const metadata = { title: "Page not found", robots: { index: false } };

export default function NotFound() {
  return (
    <main className="band">
      <div className="wrap max-w-[720px]">
        <span className="eyebrow">404</span>
        <h1 className="text-h2 mt-5 mb-4">That page isn&rsquo;t here.</h1>
        <p className="lede mb-7">
          It may have moved, or a role page may have been taken down because
          too few postings were left in it.
        </p>
        <div className="flex gap-3 flex-wrap">
          <Link href="/" className="btn">Home</Link>
          <Link href="/jobs" className="btn btn-paper">Browse jobs by role</Link>
        </div>
      </div>
    </main>
  );
}
