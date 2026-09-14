-- Password sign-up proves the address before an account exists (2026-09-14).
-- One row is one code waiting to be typed in. A correct code creates the
-- account from this row and deletes it, so an address nobody can read never
-- becomes an account - or a free credit.
--
-- The code itself is never stored, only a hash of it, and `attempts` caps how
-- many guesses one code can take. Google sign-up skips this: Google has
-- already verified the address.
CREATE TABLE IF NOT EXISTS signup_codes (
    email         TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    code_hash     TEXT NOT NULL,
    attempts      INTEGER NOT NULL DEFAULT 0,
    expires_at    TEXT NOT NULL,
    created_at    TEXT NOT NULL
);
