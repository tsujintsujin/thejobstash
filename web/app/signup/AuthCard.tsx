"use client";

import { useState, useEffect, useLayoutEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import { ALERT, SECHEAD_NOTE, SPINNER } from "../ui";
import type { Section } from "../legal/shell";
import { TERMS, TERMS_SUMMARY } from "../legal/terms";
import { PRIVACY, PRIVACY_SUMMARY } from "../legal/privacy";

type Legal = "terms" | "privacy";

const LEGAL: Record<Legal, { label: string; summary: React.ReactNode; sections: Section[] }> = {
  terms: { label: "Terms", summary: TERMS_SUMMARY, sections: TERMS },
  privacy: { label: "Privacy Policy", summary: PRIVACY_SUMMARY, sections: PRIVACY },
};

/* A button that has to read as a link: opening the legal panel is state, not
   navigation. */
const LINK_BTN =
  "font-[inherit] text-inherit bg-transparent border-0 p-0 cursor-pointer " +
  "underline underline-offset-2";

const CLOSE =
  "bg-transparent border-0 text-ink text-[20px] leading-none px-2 py-1.5 " +
  "cursor-pointer font-[inherit] opacity-60 hover:opacity-100 " +
  "focus-visible:outline focus-visible:outline-3 focus-visible:outline-flare";

type Mode = "create" | "signin";

/* ---------------------------------------------------------------------------
   The height-keyed squeeze. These pages have to fit one screen without
   scrolling, and the binding constraint is the window's HEIGHT: at 1024x640
   the card that sits comfortably at 900 tall overflowed by 118px. Each tier
   exists because the one above it measured over the viewport, so they are
   kept deliberately away from the roomier sizes.

   sq1 ≤780  ·  sq2 ≤740  ·  sq3 ≤670  ·  sq4 ≤620  (all at ≥761 wide)
--------------------------------------------------------------------------- */
const PANEL_PAD =
  "px-6 py-[22px] sq1:px-5 sq1:py-[18px] sq2:px-[18px] sq2:py-[14px] " +
  "sq3:px-[15px] sq3:py-[11px] sq4:px-[13px] sq4:py-2";

const FIELD = "mb-[11px] sq2:mb-2 sq3:mb-1.5 sq4:mb-[5px]";

const H1 =
  "text-[26px] mt-[13px] mb-3 sq1:text-[23px] sq1:my-[11px] " +
  "sq2:text-[22px] sq2:my-[9px] sq3:text-[20px] sq3:my-[7px] " +
  "sq4:text-[18px] sq4:mt-1 sq4:mb-[5px]";

/* A rule with the word sitting in a gap punched through it. */
const OR =
  "flex items-center gap-3 my-[11px] text-center " +
  "sq2:my-2 sq3:my-1.5 sq4:my-[5px] " +
  "before:content-[''] before:flex-1 before:h-0.5 before:bg-ink before:opacity-15 " +
  "after:content-[''] after:flex-1 after:h-0.5 after:bg-ink after:opacity-15";

const HINT = "text-[12.5px] font-semibold opacity-70";

/* Full width to match the submit above it, and a flex row so the mark and the
   label stay centred together rather than the text drifting off-centre
   around a floated icon. */
const GOOGLE = "btn btn-paper flex items-center justify-center gap-2.5 w-full text-center";

function GoogleMark() {
  return (
    <svg width="17" height="17" viewBox="0 0 48 48" aria-hidden="true" className="flex-none">
      <path
        fill="#4285F4"
        d="M45.12 24.5c0-1.56-.14-3.06-.4-4.5H24v8.51h11.84c-.51 2.75-2.06 5.08-4.39 6.64v5.52h7.11c4.16-3.83 6.56-9.47 6.56-16.17z"
      />
      <path
        fill="#34A853"
        d="M24 46c5.94 0 10.92-1.97 14.56-5.33l-7.11-5.52c-1.97 1.32-4.49 2.1-7.45 2.1-5.73 0-10.58-3.87-12.31-9.07H4.34v5.7C7.96 41.07 15.4 46 24 46z"
      />
      <path
        fill="#FBBC05"
        d="M11.69 28.18C11.25 26.86 11 25.45 11 24s.25-2.86.69-4.18v-5.7H4.34C2.85 17.09 2 20.45 2 24s.85 6.91 2.34 9.88l7.35-5.7z"
      />
      <path
        fill="#EA4335"
        d="M24 10.75c3.23 0 6.13 1.11 8.41 3.29l6.31-6.31C34.91 4.18 29.93 2 24 2 15.4 2 7.96 6.93 4.34 14.12l7.35 5.7c1.73-5.2 6.58-9.07 12.31-9.07z"
      />
    </svg>
  );
}

/**
 * One card for both halves of getting in. Signing in and signing up ask for
 * the same two things, so two routes meant two layouts to keep in step and a
 * full page load to correct a misclick. The mode is local state: the email
 * someone already typed survives the switch, which is the whole point.
 *
 * Layout is a split card - an ink panel of context, one column of form. The
 * form column is deliberately one column: an earlier version put the fields in
 * a narrow centred column inside a wide card and left the buttons full width
 * beneath them, which read as three different layouts stacked on each other.
 *
 * The card is NOT held to one height across the two faces. An earlier version
 * kept the sign-up-only rows in the layout on the sign-in face, hidden with
 * `visibility`, so both measured identically - but that left a 185px hole
 * between the password field and the button. The page itself no longer
 * scrolls in either mode, so there is nothing left for a rigid height to
 * protect: the card simply sizes to its contents and stays centred.
 */
export default function AuthCard({
  initialMode,
  next,
  googleReady,
  initialError = "",
  pool,
  sources,
  inModal = false,
  onClose,
}: {
  initialMode: Mode;
  next: string;
  googleReady: boolean;
  initialError?: string;
  pool: number;
  sources: number;
  /** Mounted in a dialog on some other page, so the URL is not ours to edit. */
  inModal?: boolean;
  /** The dialog's close. Rendered inside the card so it travels with it. */
  onClose?: () => void;
}) {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState(initialError);
  const [busy, setBusy] = useState(false);

  // The legal panel. `legalTab` outlives `legalOpen` so the text stays put
  // while the panel slides back out.
  const [legalOpen, setLegalOpen] = useState(false);
  const [legalTab, setLegalTab] = useState<Legal>("terms");
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const agreeRef = useRef<HTMLInputElement>(null);

  function showLegal(t: Legal) {
    setLegalTab(t);
    setLegalOpen(true);
  }

  const creating = mode === "create";

  // The sign-in face is shorter. Holding it at the create face's measured
  // height keeps the card from jumping when the tabs switch; everything in the
  // form column is top-aligned, so the spare room lands below the last line.
  const cardRef = useRef<HTMLDivElement>(null);
  const [createH, setCreateH] = useState(0);
  useLayoutEffect(() => {
    if (creating && cardRef.current) setCreateH(cardRef.current.offsetHeight);
  }, [creating]);

  // Google is a full-page redirect, not a popup: after Google's pages a popup
  // can no longer close itself (see the callback route).
  function openGoogle(e: React.MouseEvent<HTMLAnchorElement>) {
    // The same agreement the form's required checkbox enforces; this link
    // sits outside the form, so it has to ask for it itself.
    if (agreeRef.current && !agreeRef.current.checked) {
      e.preventDefault();
      agreeRef.current.reportValidity();
    }
  }

  function switchTo(m: Mode) {
    if (m === mode || busy) return;
    setMode(m);
    setErr("");
    setPending(false); // the code screen belongs to sign-up, not to sign-in
    // The URL follows the card so a reload, a back button or a shared link all
    // land on the face the person was actually looking at. In a dialog it does
    // not: the address bar belongs to the page underneath.
    if (inModal) return;
    const parts = [
      m === "signin" ? "mode=signin" : "",
      next === "/dashboard" ? "" : `next=${encodeURIComponent(next)}`,
    ].filter(Boolean);
    window.history.replaceState(
      null,
      "",
      `/signup${parts.length ? `?${parts.join("&")}` : ""}`
    );
  }

  // Password sign-up is two steps: the form emails a code, and the account is
  // created when the code comes back. `pending` is the second step on screen.
  const [pending, setPending] = useState(false);
  const [code, setCode] = useState("");
  const [note, setNote] = useState("");

  /** One POST for every step. Null means the error is already on screen. */
  async function post(url: string, payload: object) {
    setErr("");
    setBusy(true);
    // fetch rejects outright when the server is unreachable; without this the
    // button stays spinning and Next paints its error overlay.
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).catch(() => null);
    if (!r) {
      setBusy(false);
      setErr("Couldn't reach the server. Check your connection and try again.");
      return null;
    }
    const j = (await r.json().catch(() => ({}))) as any;
    if (!r.ok) {
      setBusy(false);
      setErr(j.error || "Something went wrong.");
      return null;
    }
    return j;
  }

  function go(j: any, fallback: string) {
    // Deliberately leaving `busy` set: the next page is a server render and
    // takes a beat, and a button snapping back reads as a failure.
    router.push(j.redirect || fallback);
    router.refresh();
  }

  function awaitCode(sentence: string) {
    setBusy(false);
    setCode("");
    setNote(`${sentence} ${email}. It expires in 10 minutes.`);
    setPending(true);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const j = creating
      ? await post("/api/auth/signup", { email, password })
      : await post("/api/auth/login", { email, password, next });
    if (!j) return;
    if (j.verify) return awaitCode("We sent a 6-digit code to");
    go(j, creating ? "/upload" : "/dashboard");
  }

  async function verify(e: React.FormEvent) {
    e.preventDefault();
    const j = await post("/api/auth/signup/verify", { email, code });
    if (j) go(j, "/upload");
  }

  async function resend() {
    const j = await post("/api/auth/signup", { email, password });
    if (j) awaitCode("We sent a new code to");
  }

  function changeEmail() {
    setPending(false);
    setErr("");
  }

  const googleLabel = creating ? "Sign up with Google" : "Sign in with Google";

  /* Tab selection is STATE, not an action, so it inverts to ink rather than
     taking the action colour — which the submit button below owns. */
  const tab = (on: boolean) =>
    "font-[inherit] font-extrabold text-[13px] uppercase tracking-[0.07em] " +
    "px-2 py-[11px] border-0 cursor-pointer transition-colors duration-100 " +
    "sq1:py-[9px] sq3:py-[7px] sq3:text-xs " +
    "focus-visible:outline focus-visible:outline-3 focus-visible:outline-flare " +
    "focus-visible:-outline-offset-3 " +
    (on ? "bg-ink text-bone" : "bg-transparent text-ink hover:bg-bone");

  return (
    <>
    {/* With the legal panel open the card drops its ink panel, narrows to the
        form column and slides to the centre of the right half. Both mounts
        centre the card in the viewport, so 25vw is exactly that distance. */}
    <div
      ref={cardRef}
      style={{ minHeight: creating ? undefined : createH || undefined }}
      className={`card p-0 shadow-brut-lg grid overflow-hidden mx-auto
                  transition-[transform,max-width] duration-300 ease-out
                  max-[760px]:grid-cols-1 max-[760px]:translate-x-0
                  ${legalOpen
                    ? "grid-cols-1 max-w-[min(440px,calc(50vw-48px))] translate-x-[25vw]"
                    : "grid-cols-[0.82fr_1fr] max-w-[960px]"}`}
    >
      {/* Centred, not top-aligned: the panel carries less than the form column,
          and pinned to the top it left a dead third at the bottom of the card.
          It is also the first thing to go on a phone — it is context, not the
          task. */}
      <aside
        className={`bg-ink text-bone border-r-3 border-ink flex-col
                    justify-center max-[760px]:hidden ${PANEL_PAD}
                    ${legalOpen ? "hidden" : "flex"}`}
      >
        {/* The pitch, not the wordmark - the nav and the footer already say
            the name twice, and a third would be the only thing this panel
            contributed. */}
        <h2 className="text-[25px] font-extrabold tracking-[-0.03em] leading-[1.12]">
          Jobs that actually{" "}
          <em className="not-italic text-sun">match</em> your resume.
        </h2>

        <ul className="list-none mt-[22px] grid gap-[13px] sq1:mt-4 sq1:gap-2.5">
          {[
            <>
              <b className="text-sun">{pool.toLocaleString()}</b> live postings,
              scored against your resume overnight
            </>,
            <>
              Swept from <b className="text-sun">{sources}</b> job boards every
              morning
            </>,
            <>The near-misses too — and exactly what blocked each one</>,
          ].map((line, i) => (
            /* A sun square rather than a bullet - the system has no round
               edges. Sun rather than jade because this panel is ink: sun on
               ink is 11.1:1 against jade's 8.2:1, and these are 12.5px. */
            <li
              key={i}
              className="text-[12.5px] font-semibold leading-[1.45] opacity-90
                         pl-[15px] relative before:content-[''] before:absolute
                         before:left-0 before:top-[5px] before:w-[7px]
                         before:h-[7px] before:bg-sun"
            >
              {line}
            </li>
          ))}
        </ul>
      </aside>

      {/* In the dialog the close button sits in this column's top-right
          corner, so the tabs start lower to leave it room. */}
      <div className={`relative min-w-0 ${PANEL_PAD} ${inModal ? "!pt-12" : ""}`}>
        {onClose && (
          <button
            className={`${CLOSE} absolute top-3 right-3.5 z-10`}
            onClick={onClose}
            aria-label="Close"
          >
            ✕
          </button>
        )}
        {/* One shared frame with an internal divider, so it reads as one
            control with two faces rather than two buttons that happen to sit
            together. */}
        <div
          className="grid grid-cols-2 border-3 border-ink bg-paper"
          role="group"
          aria-label="Sign in or create an account"
        >
          <button
            type="button"
            onClick={() => switchTo("signin")}
            aria-pressed={!creating}
            className={tab(!creating)}
          >
            Sign in
          </button>
          <button
            type="button"
            onClick={() => switchTo("create")}
            aria-pressed={creating}
            className={`${tab(creating)} border-l-3 border-ink`}
          >
            Get started
          </button>
        </div>

        <h1 className={H1}>
          {pending ? "Check your email" : creating ? "Create an account" : "Welcome back"}
        </h1>

        {err && <div className={ALERT}>{err}</div>}

        {pending ? (
          <form onSubmit={verify}>
            <p className={`${HINT} mb-3`}>{note}</p>
            <div className={FIELD}>
              <label htmlFor="code" className="text-center">Code</label>
              <input
                id="code"
                type="text"
                value={code}
                required
                autoFocus
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="\d{6}"
                maxLength={6}
                placeholder="123456"
                onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                className="px-[13px] py-[11px] sq2:py-[9px] sq2:px-3 text-center
                           font-extrabold tracking-[0.35em]"
              />
            </div>
            <button
              className="btn w-full text-center sq3:px-[18px] sq3:py-2 sq3:text-sm
                         sq4:px-4 sq4:py-[7px]"
              type="submit"
              disabled={busy}
            >
              {busy && <span className={SPINNER} />}
              {busy ? "Checking…" : "Create account"}
            </button>
            <p className={`${HINT} mt-[11px] text-center`}>
              Nothing arrived?{" "}
              <button type="button" className={`${LINK_BTN} font-extrabold`} onClick={resend} disabled={busy}>
                Send a new code
              </button>
              {" · "}
              <button type="button" className={`${LINK_BTN} font-extrabold`} onClick={changeEmail} disabled={busy}>
                Use a different email
              </button>
            </p>
          </form>
        ) : (
        <>
        <form onSubmit={submit}>
          <div className={FIELD}>
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              required
              autoComplete="email"
              placeholder="you@example.com"
              onChange={(e) => setEmail(e.target.value)}
              className="px-[13px] py-[11px] sq2:py-[9px] sq2:px-3"
            />
          </div>

          <div className={FIELD}>
            <label htmlFor="password">Password</label>
            <input
              id="password"
              // The key forces a fresh node on switch. Without it the browser
              // keeps treating a new-password field as the one it just offered
              // to save, and password managers fill the wrong thing.
              key={creating ? "new" : "current"}
              type="password"
              value={password}
              required
              minLength={creating ? 8 : undefined}
              autoComplete={creating ? "new-password" : "current-password"}
              placeholder={creating ? "At least 8 characters" : "Your password"}
              onChange={(e) => setPassword(e.target.value)}
              className="px-[13px] py-[11px] sq2:py-[9px] sq2:px-3"
            />
          </div>

          <button
            className="btn w-full text-center sq3:px-[18px] sq3:py-2 sq3:text-sm
                       sq4:px-4 sq4:py-[7px]"
            type="submit"
            disabled={busy}
          >
            {busy && <span className={SPINNER} />}
            {busy
              ? creating
                ? "Creating…"
                : "Signing in…"
              : creating
                ? "Create account"
                : "Sign in"}
          </button>

          {/* Consent belongs at the point of collection, not three clicks away
              in a footer. Only on the create face: an existing account already
              agreed, and a second copy of it is just noise on a card that is
              fighting for vertical space. */}
          {creating && (
            <label
              className="flex items-start justify-center gap-2 mt-2.5 mb-0
                         sq3:mt-1.5 text-[12.5px] font-semibold normal-case
                         tracking-normal cursor-pointer"
            >
              {/* `required` blocks the submit natively; openGoogle checks it
                  for the Google button. */}
              <input
                ref={agreeRef}
                type="checkbox"
                required
                className="mt-0.5 w-4 h-4 flex-none accent-ink cursor-pointer"
              />
              <span className="opacity-70">
                By creating an account you agree to the{" "}
                <button type="button" className={LINK_BTN} onClick={() => showLegal("terms")}>
                  Terms
                </button>{" "}
                and the{" "}
                <button type="button" className={LINK_BTN} onClick={() => showLegal("privacy")}>
                  Privacy Policy
                </button>
                .
              </span>
            </label>
          )}
        </form>

        <div className={OR}>
          <span className="text-[11px] font-extrabold uppercase tracking-[0.12em] opacity-55">
            or
          </span>
        </div>

        {googleReady ? (
          <a
            className={GOOGLE}
            href={`/api/auth/google?next=${encodeURIComponent(next)}`}
            onClick={openGoogle}
          >
            <GoogleMark />
            {googleLabel}
          </a>
        ) : (
          <>
            {/* A dead control with no explanation reads as a broken page.
                Say why, once, in the place the disappointment happens. */}
            <button
              className={GOOGLE}
              type="button"
              disabled
              aria-describedby="google-off"
            >
              <GoogleMark />
              {googleLabel}
            </button>
            <p className={`${HINT} mt-1.5`} id="google-off">
              Not switched on yet — use an email and password for now.
            </p>
          </>
        )}

        {/* Someone who created their account with Google has no password, and
            the sign-in endpoint deliberately will not say so: an error that
            distinguishes "no password" from "wrong password" is a way to test
            which addresses have accounts. This sits outside the error instead,
            where it tells nobody anything they did not already type. */}
        {!creating && googleReady && (
          <p className={`${HINT} mt-2 text-center`}>
            Signed up with Google? Use the button above.
          </p>
        )}

        <p
          className={`${HINT} mt-[11px] text-center sq2:mt-2 sq3:mt-1.5
                      sq3:text-[11.5px] sq4:mt-[5px]`}
        >
          {creating ? "Already have one? " : "No account yet? "}
          {/* A button that has to read as a link, because switching the card
              is state, not navigation - an <a href> here would be a lie the
              back button exposes. */}
          <button
            type="button"
            className="font-[inherit] font-extrabold text-inherit bg-transparent
                       border-0 p-0 cursor-pointer underline underline-offset-2"
            onClick={() => switchTo(creating ? "signin" : "create")}
          >
            {creating ? "Sign in" : "Get started"}
          </button>
        </p>
        </>
        )}
      </div>
    </div>

    {/* Portalled: a fixed panel inside the card would be positioned against
        the card's transform, not the screen. It stays mounted so it can slide
        out as well as in; `inert` keeps it out of reach while hidden. */}
    {mounted &&
      createPortal(
        <aside
          role="dialog"
          aria-label="Terms and Privacy Policy"
          inert={!legalOpen}
          className={`fixed inset-y-0 left-0 z-[110] w-1/2 max-[760px]:w-full
                      bg-bone text-ink border-r-3 border-ink flex flex-col
                      transition-transform duration-300 ease-out
                      ${legalOpen ? "translate-x-0" : "-translate-x-full"}`}
        >
          <div className="flex border-b-3 border-ink bg-paper">
            <div className="grid grid-cols-2 flex-1" role="group" aria-label="Terms or Privacy Policy">
              {(["terms", "privacy"] as const).map((t, i) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setLegalTab(t)}
                  aria-pressed={legalTab === t}
                  className={`${tab(legalTab === t)} ${i ? "border-l-3 border-ink" : ""}`}
                >
                  {LEGAL[t].label}
                </button>
              ))}
            </div>
            <button
              type="button"
              className={`${CLOSE} border-l-3 border-ink !px-4`}
              onClick={() => setLegalOpen(false)}
              aria-label="Close Terms and Privacy Policy"
            >
              ✕
            </button>
          </div>

          {/* Keyed so switching tabs starts the new document at the top. */}
          <div key={legalTab} className="flex-1 overflow-y-auto p-6 max-[560px]:p-4">
            <div className="card bg-jade shadow-brut mb-7">
              <h2 className="text-h3 mb-3">The short version</h2>
              <div className="text-[15px] leading-[1.6]">{LEGAL[legalTab].summary}</div>
            </div>
            {LEGAL[legalTab].sections.map((s, i) => (
              <section key={s.id} id={s.id}>
                <div className="sechead bg-paper">
                  <h2 className="text-h3">{s.title}</h2>
                  <em className={SECHEAD_NOTE}>{String(i + 1).padStart(2, "0")}</em>
                </div>
                {s.body}
              </section>
            ))}
          </div>
        </aside>,
        document.body
      )}
    </>
  );
}
