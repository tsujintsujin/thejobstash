"use client";

import { useState, useEffect } from "react";
import AuthCard from "./signup/AuthCard";

/**
 * The signup/sign-in card in a dialog, for the marketing page.
 *
 * Nothing scores a resume without an account behind it any more, but sending
 * somebody off the page to a form before they have seen what the product does
 * is the bounce the old free-scan modal existed to avoid. So the same
 * `AuthCard` the /signup page renders opens here instead — one implementation,
 * two mounts. `inModal` only suppresses the tab switch's URL rewrite, which
 * would otherwise put `/signup` in the address bar of a page you are still on.
 */
export default function AuthModal({
  label,
  googleReady,
  pool,
  sources,
}: {
  label: string;
  googleReady: boolean;
  pool: number;
  sources: number;
}) {
  const [open, setOpen] = useState(false);

  // The page behind must not scroll under the dialog. Only the X closes it:
  // a stray click on the backdrop or an Escape would throw away a half-typed
  // form.
  useEffect(() => {
    if (!open) return;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <>
      <button className="btn" onClick={() => setOpen(true)}>
        {label}
      </button>

      {open && (
        <div
          className="fixed inset-0 z-[100] bg-ink/60 flex items-center
                     justify-center p-5 animate-fade overflow-y-auto"
        >
          <div
            className="relative w-full max-w-[960px] animate-pop my-auto"
            role="dialog"
            aria-modal="true"
            aria-label="Create an account or sign in"
          >
            {/* The close button lives inside the card, over the form column,
                so it moves with the card when the legal panel slides it
                aside. */}
            <AuthCard
              initialMode="create"
              next="/dashboard"
              googleReady={googleReady}
              pool={pool}
              sources={sources}
              inModal
              onClose={() => setOpen(false)}
            />
          </div>
        </div>
      )}
    </>
  );
}
