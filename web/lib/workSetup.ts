/**
 * Work setup, as the user picks it on the dashboard.
 *
 * A resume almost never says whether someone wants remote, hybrid or onsite
 * work, so this is the user's to set rather than the parser's to guess.
 *
 * It is stored as the two booleans the scorer already reads (Profile in
 * profiles.py), never as a field of its own: delivery.py rebuilds the profile
 * with Profile(**profile_json), so an unknown key would fail every run.
 *
 *   remote   remote_only  -  local onsite roles are blocked
 *   hybrid   remote_only + wants_local_onsite  -  local roles welcome,
 *            postings that say "onsite only" still blocked
 *   onsite   wants_local_onsite  -  nothing blocked for being onsite
 */
export const WORK_SETUPS = ["remote", "hybrid", "onsite"] as const;
export type WorkSetup = (typeof WORK_SETUPS)[number];

export const WORK_SETUP_LABEL: Record<WorkSetup, string> = {
  remote: "Remote",
  hybrid: "Hybrid",
  onsite: "Onsite",
};

export function workSetupOf(p: {
  remote_only?: boolean;
  wants_local_onsite?: boolean;
}): WorkSetup {
  if (!p.wants_local_onsite) return "remote";
  return p.remote_only === false ? "onsite" : "hybrid";
}

export function workSetupFlags(s: WorkSetup) {
  return {
    remote_only: s !== "onsite",
    wants_local_onsite: s !== "remote",
  };
}
