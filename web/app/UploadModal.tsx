"use client";

import { useState, useEffect } from "react";
import UploadCard from "./UploadCard";

/**
 * The resume upload card in a dialog, for a signed-in visitor on the
 * marketing page.
 *
 * Same component the /upload page renders, mounted with `inModal` so it drops
 * the page band and the Back link. Uploading is the thing this site asks of
 * you, so the signed-in hero offers it directly rather than sending you to the
 * dashboard to look for it.
 */
export default function UploadModal({ label }: { label: string }) {
  const [open, setOpen] = useState(false);

  // Escape closes, and the page behind must not scroll under the dialog.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
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
          onClick={(e) => e.target === e.currentTarget && setOpen(false)}
        >
          <div
            className="relative w-full max-w-narrow animate-pop my-auto"
            role="dialog"
            aria-modal="true"
            aria-label="Upload your resume"
          >
            <button
              className="absolute top-2 right-2.5 z-10 bg-transparent border-0
                         text-ink text-[19px] leading-none px-1.5 py-1
                         cursor-pointer font-[inherit] opacity-60
                         hover:opacity-100
                         focus-visible:outline focus-visible:outline-3
                         focus-visible:outline-flare"
              onClick={() => setOpen(false)}
              aria-label="Close"
            >
              ✕
            </button>

            <UploadCard inModal />
          </div>
        </div>
      )}
    </>
  );
}
