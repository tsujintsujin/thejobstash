// Refuses to deploy anything that is not committed and pushed to GitHub.
//
// wrangler uploads whatever files are sitting on disk - it never looks at git.
// That means production could run code that exists in no commit, on no branch,
// nowhere but one hard drive. This makes the deploy path go through git.
//
// Runs automatically: npm hooks `predeploy` before `deploy`.
// Genuine emergency override: ALLOW_DIRTY_DEPLOY=1 npm run deploy
const { execSync } = require("node:child_process");

const git = (cmd) => execSync(`git ${cmd}`, { encoding: "utf8" }).trim();
const die = (msg) => {
  console.error(`\n  DEPLOY BLOCKED\n\n${msg}\n`);
  process.exit(1);
};

if (process.env.ALLOW_DIRTY_DEPLOY === "1") {
  console.warn("\n  ALLOW_DIRTY_DEPLOY=1 - deploying code that may exist nowhere but this disk.\n");
  process.exit(0);
}

const dirty = git("status --porcelain");
if (dirty) {
  const files = dirty.split("\n");
  die(
    `${files.length} uncommitted change(s). Production would run code that is in no commit:\n\n` +
      files.slice(0, 10).map((f) => `    ${f}`).join("\n") +
      (files.length > 10 ? `\n    ...and ${files.length - 10} more` : "") +
      `\n\n  Commit them, then deploy.`
  );
}

const branch = git("rev-parse --abbrev-ref HEAD");
const head = git("rev-parse HEAD");

let remote;
try {
  remote = git(`rev-parse origin/${branch}`);
} catch {
  die(`Branch '${branch}' is not on GitHub yet.\n\n    git push -u origin ${branch}`);
}

if (remote !== head) {
  const ahead = git(`rev-list --count origin/${branch}..HEAD`);
  if (ahead !== "0")
    die(`${ahead} commit(s) not pushed. GitHub would not have the code you are about to ship.\n\n    git push`);
}

console.log(`\n  deploying ${branch} @ ${head.slice(0, 7)} - committed and on GitHub\n`);
