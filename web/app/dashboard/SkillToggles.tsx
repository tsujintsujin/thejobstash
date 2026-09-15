"use client";

import { useState } from "react";

/**
 * The skills read from the resume, each one a switch.
 *
 * A parsed resume is a guess, and some of its guesses are wrong or stale — a
 * language you used once, a tool you never want to be sent jobs for again.
 * Clicking a skill greys it out and it stops counting towards scoring;
 * clicking it again brings it back.
 *
 * The state is optimistic: the tag flips immediately and the write is sent
 * after. A failed write puts the tag back rather than leaving the page
 * claiming something the database does not say.
 */
export default function SkillToggles({
  skills,
  disabled,
}: {
  skills: string[];
  disabled: string[];
}) {
  const [off, setOff] = useState<string[]>(() =>
    disabled.map((s) => s.toLowerCase())
  );
  const [err, setErr] = useState("");

  async function toggle(skill: string) {
    const key = skill.toLowerCase();
    const wasOff = off.includes(key);
    const next = wasOff ? off.filter((s) => s !== key) : [...off, key];
    setOff(next);
    setErr("");

    const r = await fetch("/api/skills", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ skill, enabled: wasOff }),
    }).catch(() => null);
    if (!r?.ok) {
      setOff(off);
      setErr("Couldn't save that. Try again.");
    }
  }

  const live = skills.length - off.length;

  return (
    <>
      <p className="text-[12px] font-semibold opacity-65 mt-3 leading-[1.45]">
        Click a skill to leave it out of scoring. {live} of {skills.length} are
        counting.
      </p>
      <div className="flex gap-1.5 flex-wrap mt-2">
        {skills.map((s) => {
          const isOff = off.includes(s.toLowerCase());
          return (
            <button
              key={s}
              type="button"
              onClick={() => toggle(s)}
              aria-pressed={!isOff}
              title={isOff ? `Count ${s} again` : `Leave ${s} out of scoring`}
              className={`tag cursor-pointer font-[inherit] ${
                isOff
                  ? "opacity-40 line-through bg-transparent"
                  : "hover:bg-lime"
              }`}
            >
              {s}
            </button>
          );
        })}
      </div>
      {err && (
        <p className="text-[12px] font-bold mt-2">{err}</p>
      )}
    </>
  );
}
