import type { Config } from "tailwindcss";
import plugin from "tailwindcss/plugin";

/* TheJobStash — neo-brutalist design tokens.
   ---------------------------------------------------------------------------
   The palette is role-named, not hue-named, because the previous system's one
   real defect was semantic: `coral` was simultaneously the primary button, the
   "this job was blocked" colour, and the FAQ band. The action colour and the
   failure colour were the same colour, so nothing on the page could tell you
   whether it wanted a click or was reporting bad news.

   Ten tokens, five roles:

     ink     near-black. Every border, every rule, all body text, the dark
             cards, the footer. Previously a deep indigo; flattened to black
             so the accents are the only thing carrying hue.
     bone    warm newsprint. The page ground.
     paper   white. Cards sitting on bone.

     azure   IDENTITY. The hero and the closing call to action — the two
             full-width blue blocks the page opens and closes on. It is a
             ground, never a button; flare still owns every press.
     flare   ACTION and nothing else. Primary buttons, focus rings, the one
             thing on a band you are meant to press.
     sun     ATTENTION. Near-misses, blockers, the marquee, warnings — the
             "here is what is in the way" colour.
     jade    POSITIVE. Strong matches, score chips, good news.
     lime    THE NUMBER. The single figure a block exists to state: the live
             pool, the count that survived scoring, the matches found. It is
             the brightest thing in the system, so only one card per band
             ever wears it.
     grape   SHOWCASE. One dark saturated band — "four steps" — carrying white
             cards. It is a ground only; nothing small is ever grape.
     coral   QUIET WARM. The FAQ band. Distinct from flare on purpose: this is
             a long stretch of reading that wants warmth, not a call to press.
             Lighter and pinker than flare so the two never read as the same
             colour sitting next to each other.

   Contrast, measured:
     ink on flare 5.16  ·  ink on sun 10.05  ·  ink on jade 9.28
     ink on lime 14.06  ·  ink on coral 6.57
     ink on bone 15.75  ·  ink on paper 17.99  ·  bone on ink 15.75
     bone on azure 4.98 ·  bone on grape 4.93
     sun on ink 10.05 (the auth panel, at 12.5px)

   Flare is the one value that was tuned rather than chosen. It doubles as the
   focus ring, and a ring has to clear 3:1 against what sits OUTSIDE it as
   well as the ink border inside it. At the original #FF6B4A that outer figure
   was 2.82 against paper and 2.46 against bone - under WCAG 2.2. Darkening to
   #EE5130 lifts those to 3.50 and 3.05 while ink text on a flare button still
   clears AA at 5.16. One token does both jobs.

   azure and grape are the only two accents that carry bone text; both clear
   4.5:1 and both are used as full-band grounds where the type is large. Every
   other accent is a background for ink text and nothing else. No accent
   carries white text — white on jade is 2.09:1 and white on sun is 1.54:1.

   Accent-against-accent contrast is deliberately low. Colour is not what
   separates two adjacent blocks here; the 3px ink border is. */

export default {
  content: ["./app/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#16161C",
        bone: "#F5EFE3",
        paper: "#FFFFFF",
        azure: "#2B57EC",
        flare: "#EE5130",
        sun: "#F5B92E",
        jade: "#3ECFB4",
        lime: "#CBF24F",
        grape: "#7B3FE8",
        coral: "#F0796A",
        /* Hairlines and dividers: ink at low alpha, so they tint with the
           ground beneath instead of laying grey over it. */
        "ink-line": "rgba(22,22,28,.14)",
        "bone-line": "rgba(245,239,227,.22)",
      },
      /* Hard offset shadows — no blur, ever. The shadow is a second copy of
         the border, not a light source. */
      boxShadow: {
        brut: "5px 5px 0 #16161C",
        "brut-sm": "3px 3px 0 #16161C",
        "brut-xs": "2px 2px 0 #16161C",
        "brut-lg": "8px 8px 0 #16161C",
        /* The one coloured shadow: the sample digest on the blue hero, where
           an ink shadow would vanish into the band behind it. */
        "brut-lime": "8px 8px 0 #CBF24F",
      },
      borderWidth: { 3: "3px" },
      fontFamily: {
        sans: [
          "Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI",
          "Helvetica Neue", "Arial", "sans-serif",
        ],
        mono: ["ui-monospace", "SF Mono", "Menlo", "Consolas", "monospace"],
      },
      fontSize: {
        display: ["clamp(42px,7vw,82px)", { lineHeight: "1.02", letterSpacing: "-0.03em", fontWeight: "800" }],
        h2: ["clamp(30px,4.4vw,48px)", { lineHeight: "1.02", letterSpacing: "-0.03em", fontWeight: "800" }],
        h3: ["clamp(20px,2.4vw,26px)", { lineHeight: "1.05", letterSpacing: "-0.02em", fontWeight: "800" }],
      },
      keyframes: {
        slide: { from: { transform: "translateX(0)" }, to: { transform: "translateX(-50%)" } },
        fade: { from: { opacity: "0" }, to: { opacity: "1" } },
        pop: {
          from: { transform: "translateY(10px) scale(.985)", opacity: ".6" },
          to: { transform: "none", opacity: "1" },
        },
      },
      animation: {
        slide: "slide 34s linear infinite",
        fade: "fade .14s ease",
        pop: "pop .16s cubic-bezier(.2,.8,.3,1)",
        spin: "spin .7s linear infinite",
      },
      maxWidth: { wrap: "1120px", narrow: "640px", auth: "880px" },
    },
  },
  /* Height-keyed breakpoints for the single-card pages (login, signup,
     upload). Those pages have to fit one screen without scrolling, and the
     constraint is the window's HEIGHT, not its width: at 1024x640 the card
     that sits comfortably at 900 tall overflowed by 118px. Each tier below
     exists because the one above it measured over the viewport.

     These are variants, NOT entries in `theme.screens`, and that is load
     bearing. A single `{ raw: ... }` object anywhere in `theme.screens` makes
     Tailwind silently drop the `min-*` and `max-*` variants for the whole
     project - it warns and carries on. globals.css uses `max-[560px]:` and
     `max-[760px]:` seventeen times, so every one of them stopped existing and
     the stylesheet failed to build. Registering them here leaves
     `theme.screens` all-strings, which is the condition those variants need.

     Defined highest-to-lowest so the cascade order matches the old screens
     block: a viewport 600px tall matches all four, and the last one wins. */
  plugins: [
    plugin(({ addVariant }) => {
      addVariant("sq1", "@media (min-width:761px) and (max-height:780px)");
      addVariant("sq2", "@media (min-width:761px) and (max-height:740px)");
      addVariant("sq3", "@media (min-width:761px) and (max-height:670px)");
      addVariant("sq4", "@media (min-width:761px) and (max-height:620px)");
    }),
  ],
} satisfies Config;
