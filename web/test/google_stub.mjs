/**
 * A stand-in for Google's OAuth endpoints, for testing sign-in locally.
 *
 * Creating a real OAuth client needs a Google Cloud project that only the
 * account owner can make. Without this, the branches that actually matter -
 * creating an account, linking one that already exists, and *refusing* to link
 * an unverified address - could not be run even once before shipping.
 *
 * It speaks only the two endpoints our callback touches:
 *
 *   GET  /o/oauth2/v2/auth   bounce straight back to redirect_uri with a code
 *   POST /token              swap that code for an id_token
 *
 * The identity is chosen by the test through `POST /_identity` just before it
 * starts a sign-in. The claims are then carried *inside the code*, so the
 * token exchange holds no state of its own and two tests cannot cross wires.
 *
 * The id_token is a real JWT shape with a junk signature. That is honest about
 * what the callback does: it reads the payload of a token handed to it
 * directly by the token endpoint over TLS, and does not verify the signature.
 * If that ever changes to accept a token from a browser, this stub must start
 * signing properly - and the test that says so should fail first.
 *
 *   node test/google_stub.mjs [port]
 */
import http from "node:http";

const PORT = Number(process.argv[2] || 3210);

const b64u = (o) => Buffer.from(JSON.stringify(o), "utf8").toString("base64url");
const unb64u = (s) => JSON.parse(Buffer.from(s, "base64url").toString("utf8"));

/** What the next sign-in will present. Overwritten by POST /_identity. */
let identity = { sub: "stub-sub-default", email: "stub@demo.test", email_verified: true };

function body(req) {
  return new Promise((res) => {
    let b = "";
    req.on("data", (c) => (b += c));
    req.on("end", () => res(b));
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);

  // --- test control -------------------------------------------------------
  if (url.pathname === "/_identity" && req.method === "POST") {
    identity = { ...JSON.parse((await body(req)) || "{}") };
    res.writeHead(200, { "Content-Type": "application/json" });
    return res.end(JSON.stringify({ ok: true, identity }));
  }

  // --- Google's consent screen -------------------------------------------
  if (url.pathname === "/o/oauth2/v2/auth") {
    const redirect = url.searchParams.get("redirect_uri") || "";
    const state = url.searchParams.get("state") || "";
    const back = new URL(redirect);

    // Someone pressing Cancel on Google's screen.
    if (identity.deny) {
      back.searchParams.set("error", "access_denied");
      back.searchParams.set("state", state);
      res.writeHead(302, { Location: back.toString() });
      return res.end();
    }

    back.searchParams.set("code", b64u(identity));
    // A test can hand back a state that doesn't match the cookie, which is
    // what a forged callback URL looks like from the server's side.
    back.searchParams.set("state", identity.forgeState ?? state);
    res.writeHead(302, { Location: back.toString() });
    return res.end();
  }

  // --- code -> tokens -----------------------------------------------------
  if (url.pathname === "/token" && req.method === "POST") {
    const form = new URLSearchParams(await body(req));
    let claims;
    try {
      claims = unb64u(form.get("code") || "");
    } catch {
      res.writeHead(400, { "Content-Type": "application/json" });
      return res.end(JSON.stringify({ error: "invalid_grant" }));
    }

    // Google rejects a bad client secret. Proving we send one at all means
    // proving this endpoint is reached with it.
    if (!form.get("client_secret")) {
      res.writeHead(401, { "Content-Type": "application/json" });
      return res.end(JSON.stringify({ error: "invalid_client" }));
    }
    if (claims.tokenFails) {
      res.writeHead(400, { "Content-Type": "application/json" });
      return res.end(JSON.stringify({ error: "invalid_grant" }));
    }
    if (claims.noIdToken) {
      res.writeHead(200, { "Content-Type": "application/json" });
      return res.end(JSON.stringify({ access_token: "stub" }));
    }

    const payload = { sub: claims.sub, email: claims.email, iss: "stub" };
    if (claims.email_verified !== undefined) {
      payload.email_verified = claims.email_verified;
    }
    const id_token = [
      b64u({ alg: "RS256", typ: "JWT" }),
      b64u(payload),
      "not-a-real-signature",
    ].join(".");

    res.writeHead(200, { "Content-Type": "application/json" });
    return res.end(JSON.stringify({ id_token, access_token: "stub" }));
  }

  res.writeHead(404).end("no");
});

server.listen(PORT, () => console.log(`google stub on http://localhost:${PORT}`));
