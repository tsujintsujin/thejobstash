"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

/**
 * Remove one past digest from the list.
 *
 * Deletion is permanent and the row is the only pointer to the file, so the
 * trash arms rather than fires: the first click swaps it for an explicit
 * "Remove?" next to a way out. Deliberately not window.confirm() — a native
 * modal freezes the renderer, Chrome lets a user suppress it after the second
 * one, and it cannot say the one thing that actually reassures people here,
 * which is that the emailed copy is untouched.
 */
export default function DeleteDigest({ id, day }: { id: string; day: string }) {
  const router = useRouter();
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function remove() {
    setBusy(true);
    setErr("");
    const r = await fetch(`/api/download/${id}`, { method: "DELETE" });
    if (!r.ok) {
      setBusy(false);
      setArmed(false);
      return setErr(await r.text().catch(() => "Something went wrong."));
    }
    // The row is gone, so the server render drops this card entirely. Leave
    // busy set: unmounting is the success state.
    router.refresh();
  }

  if (armed) {
    return (
      <span className="flex items-center gap-[7px]">
        <span className="text-[12.5px] font-semibold opacity-70 max-[560px]:hidden">
          Email copy stays
        </span>
        <button
          className="btn btn-ink btn-sm"
          onClick={remove}
          disabled={busy}
          aria-label={`Confirm removing the ${day} digest`}
        >
          {busy ? "Removing…" : "Remove?"}
        </button>
        <button
          className="btn btn-paper btn-sm"
          onClick={() => setArmed(false)}
          disabled={busy}
        >
          Keep
        </button>
      </span>
    );
  }

  return (
    <span className="flex items-center gap-[7px]">
      {err && (
        <span className="text-[12.5px] font-bold max-w-[220px]">{err}</span>
      )}
      <button
        className="btn btn-paper btn-sm"
        onClick={() => setArmed(true)}
        title="Remove this digest"
        aria-label={`Remove the ${day} digest`}
      >
        <svg
          viewBox="0 0 24 24"
          width="15"
          height="15"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          aria-hidden="true"
          className="align-[-2px]"
        >
          <path d="M4 6h16M10 6V4h4v2M6 6l1 14h10l1-14M10 10v7M14 10v7" />
        </svg>
      </button>
    </span>
  );
}
