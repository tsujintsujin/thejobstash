"use client";

import { useEffect, useRef, useState } from "react";
import { WORK_SETUPS, WORK_SETUP_LABEL, WorkSetup } from "@/lib/workSetup";

/**
 * Remote / hybrid / onsite. Optimistic like SkillToggles: the choice shows
 * at once, and a failed write puts the old one back.
 *
 * A listbox of our own rather than a <select>, whose open menu is drawn by
 * the OS and cannot wear the site's borders. Keyboard: arrows move, Enter or
 * Space picks, Escape closes.
 */
export default function WorkSetupSelect({ initial }: { initial: WorkSetup }) {
  const [value, setValue] = useState<WorkSetup>(initial);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [err, setErr] = useState("");
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [open]);

  function show() {
    setActive(WORK_SETUPS.indexOf(value));
    setOpen(true);
  }

  async function change(next: WorkSetup) {
    setOpen(false);
    button.current?.focus();
    if (next === value) return;
    const prev = value;
    setValue(next);
    setErr("");
    const r = await fetch("/api/work-setup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ setup: next }),
    }).catch(() => null);
    if (!r?.ok) {
      setValue(prev);
      setErr("Couldn't save. Try again.");
    }
  }

  function onKey(e: React.KeyboardEvent) {
    const n = WORK_SETUPS.length;
    if (!open) {
      if (["ArrowDown", "ArrowUp", "Enter", " "].includes(e.key)) {
        e.preventDefault();
        show();
      }
      return;
    }
    if (e.key === "ArrowDown") setActive((a) => (a + 1) % n);
    else if (e.key === "ArrowUp") setActive((a) => (a - 1 + n) % n);
    else if (e.key === "Enter" || e.key === " ") change(WORK_SETUPS[active]);
    else if (e.key === "Escape" || e.key === "Tab") setOpen(false);
    else return;
    if (e.key !== "Tab") e.preventDefault();
  }

  return (
    <div ref={root} className="relative" onKeyDown={onKey}>
      <button
        ref={button}
        type="button"
        aria-label="Work setup"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => (open ? setOpen(false) : show())}
        /* Same type as the facts beside it; the dashed rule and the arrow
           are the only hint that this one can be changed. */
        className="w-full flex items-center justify-between gap-2 bg-transparent
                   border-0 border-b-2 border-dashed border-ink p-0 text-left
                   text-[19px] leading-[1.45] font-extrabold tracking-[-0.02em]
                   cursor-pointer focus-visible:outline-2
                   focus-visible:outline-offset-2 focus-visible:outline-flare"
      >
        {WORK_SETUP_LABEL[value]}
        <svg
          aria-hidden
          viewBox="0 0 12 8"
          className={`w-3 h-2 flex-none transition-transform ${open ? "rotate-180" : ""}`}
        >
          <path d="M1 1l5 5 5-5" fill="none" stroke="currentColor" strokeWidth="2.5" />
        </svg>
      </button>

      {open && (
        <ul
          role="listbox"
          aria-label="Work setup"
          className="absolute left-0 right-0 top-full mt-2 z-20 bg-paper
                     border-2 border-ink shadow-brut-sm"
        >
          {WORK_SETUPS.map((s, i) => (
            <li
              key={s}
              role="option"
              aria-selected={s === value}
              onPointerEnter={() => setActive(i)}
              onClick={() => change(s)}
              className={`flex items-center justify-between px-3 py-2.5
                          text-[15px] font-extrabold cursor-pointer
                          border-b-2 border-ink last:border-b-0
                          ${i === active ? "bg-sun" : ""}`}
            >
              {WORK_SETUP_LABEL[s]}
              {s === value && <span aria-hidden>✓</span>}
            </li>
          ))}
        </ul>
      )}
      {err && <span className="text-[12px] font-bold block mt-1">{err}</span>}
    </div>
  );
}
