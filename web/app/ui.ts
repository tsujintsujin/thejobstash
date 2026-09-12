/**
 * Shared utility strings.
 *
 * These are the compositions that recur across pages but are not worth a
 * `@layer components` class, because they carry no state and no variants —
 * they are just a long class list that would otherwise drift between five
 * files. Anything with a hover, an open state or a disabled state lives in
 * globals.css instead.
 *
 * Colour decisions deliberately stay OUT of here. A band's accent is chosen
 * at the element that wears it so the page reads top to bottom, which is the
 * whole reason the old stylesheet's `background: var(--sky)` scattered across
 * fourteen inline styles was hard to reason about.
 */

/* Responsive grids. 4-up and 3-up both collapse to 2 then 1. */
export const G4 =
  "grid gap-4 grid-cols-4 max-[900px]:grid-cols-2 max-[620px]:grid-cols-1";
export const G3 =
  "grid gap-4 grid-cols-3 max-[900px]:grid-cols-2 max-[620px]:grid-cols-1";

/* A big number with a caption under it. */
export const STAT = "border-3 border-ink shadow-brut text-ink px-5 py-[18px]";
export const STAT_N =
  "block text-[38px] font-extrabold tracking-[-0.03em] leading-none";
export const STAT_L =
  "text-[11px] font-extrabold uppercase tracking-[0.09em] opacity-70";

/* Three alert states, none of which uses the action colour.
   - ALERT   hard error. Inverts to ink rather than turning red, because red
             here is flare, and flare everywhere else means "this is the
             button". An error styled as the primary action is exactly the
             collision this palette exists to remove.
   - ALERT_OK    good news, so it wears the positive colour.
   - ALERT_INFO  neutral aside; carries the border and nothing else. */
const ALERT_BASE =
  "border-3 border-ink px-[15px] py-[13px] text-sm font-bold mb-[18px]";
export const ALERT = `${ALERT_BASE} bg-ink text-bone`;
export const ALERT_OK = `${ALERT_BASE} bg-jade text-ink`;
export const ALERT_INFO = `${ALERT_BASE} bg-paper text-ink`;

/* The loading dot. Its border-top is transparent, which is what makes the
   ring read as spinning rather than pulsing. */
export const SPINNER =
  "inline-block w-[15px] h-[15px] border-3 border-ink border-t-transparent " +
  "rounded-full animate-spin align-[-2px] mr-2";

/* The right-hand caption in a .sechead. `not-italic` because the markup uses
   <em> for emphasis, not for slant. */
export const SECHEAD_NOTE =
  "not-italic text-[12.5px] font-semibold opacity-80";
