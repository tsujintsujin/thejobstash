/**
 * Years of experience, as the user sets it on the dashboard, and the
 * seniority that follows from it.
 *
 * levelFromYears mirrors profiles.py level_from_years (and the fallback in
 * resume_parse.find_level). Change the cutoffs there and here together.
 */
export const MAX_YEARS = 50;

export function levelFromYears(years: number) {
  if (years <= 1) return "junior";
  if (years <= 4) return "mid";
  if (years <= 7) return "senior";
  return "lead";
}
