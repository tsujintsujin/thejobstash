-- Every run scores the whole pool fresh. Nothing records which jobs a user has
-- been shown any more: that history was left over from the daily digest, where
-- it stopped the morning email repeating itself. In a per-run product it hid a
-- user's best matches after one run, and a resume upload wiped it.
DROP TABLE IF EXISTS sent_jobs;
