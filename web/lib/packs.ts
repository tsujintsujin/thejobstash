/**
 * The only place prices live. The home page, the dashboard and checkout all
 * read this, so a price is changed once - the old plan ids were hardcoded in
 * nine files and a missed one failed silently.
 *
 * No server imports here: client components read it too.
 */
export const PACKS = [
  { id: "c3", credits: 3, php: 99 },
  { id: "c5", credits: 5, php: 149 },
  { id: "c12", credits: 12, php: 299 },
] as const;

export type Pack = (typeof PACKS)[number];

/** Every account starts with this many. The grant itself is the column
 *  default in migrations/0003_credits.sql; this is only for copy. */
export const FREE_CREDITS = 1;

// ponytail: every pack charges this while live checkout is being tested.
// Set to null to charge the real prices above.
export const TEST_PRICE_PHP: number | null = 1;

export const chargePhp = (p: Pack) => TEST_PRICE_PHP ?? p.php;

export const packById = (id: string) => PACKS.find((p) => p.id === id);
