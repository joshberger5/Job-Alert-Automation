# Roadmap: Job Alert Automation

## Overview

This roadmap covers four parallel feature branches that enhance the existing job alert pipeline. Scoring and profile configuration come first because feedback scoring (SCORE-04) is a dependency for feedback wiring (FEED-04). Fetcher hardening runs in parallel and must complete before email enhancements can reference retry/failure state. Feedback integration follows scoring and gates the weekly pattern summary. Email enhancements ship last, pulling together outputs from all three prior phases.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Scoring & Profile** - Move candidate config to YAML and implement salary filter, tertiary skill cleanup, feedback scoring, and experience gap fix
- [ ] **Phase 2: Fetchers** - Add JSearch and Oracle fetchers, verify three new ATS targets, and harden all fetchers with retry, timeouts, and correct cron schedule
- [ ] **Phase 3: Feedback Loop** - Wire vote buttons in email, implement feedback.yml workflow, add vote archival, and integrate feedback bias into scoring
- [ ] **Phase 4: Email Enhancements** - Sort jobs by score, always-send, failed fetcher section, possibly relevant section, debug JSON commit, run summary, weekly pattern summary, and missing key warnings

## Phase Details

### Phase 1: Scoring & Profile
**Goal**: Candidate preferences are externalized to config and scoring accurately reflects skills, salary floor, and experience thresholds
**Depends on**: Nothing (first phase)
**Requirements**: SCORE-01, SCORE-02, SCORE-03, SCORE-04, SCORE-05
**Success Criteria** (what must be TRUE):
  1. Editing `candidate_profile.yaml` changes preferred locations, remote policy, contract preference, and minimum salary without touching source code
  2. A job with a parseable `salary_max` below `minimum_salary` is filtered out; a job with no salary listed reaches scoring
  3. Running the pipeline produces no noisy single-occurrence or non-tech tokens in tertiary skill scoring
  4. A job matching tokens with 3+ net feedback votes receives a score adjustment visible in `jobs_debug.json`
  5. A job requiring `ideal_max + 5` years of experience is classified LARGE_GAP and filtered; one requiring `ideal_max + 3` years is classified MODERATE_GAP and filtered
**Plans**: 5 plans

Plans:
- [ ] 01-01-PLAN.md — Test scaffolds and tech_taxonomy.yaml (Wave 0)
- [ ] 01-02-PLAN.md — Extend CandidateProfile and candidate_profile.yaml; SCORE-05 tests (Wave 1)
- [ ] 01-03-PLAN.md — Salary floor filter in FilteringPolicy (Wave 2, parallel)
- [ ] 01-04-PLAN.md — Taxonomy validation in ResumeProfileBuilder (Wave 2, parallel)
- [ ] 01-05-PLAN.md — FeedbackBiasService and JobProcessingService wiring (Wave 3)

### Phase 2: Fetchers
**Goal**: All fetcher sources are expanded and every fetcher is protected by retry, wall-clock timeout, and correct detail-page timeouts
**Depends on**: Nothing (can run in parallel with Phase 1)
**Requirements**: FETCH-01, FETCH-02, FETCH-03, FETCH-04, FETCH-05, FETCH-06, FETCH-07
**Success Criteria** (what must be TRUE):
  1. A run with `JSEARCH_API_KEY` set fetches jobs from JSearch local and remote queries; a run without the key skips JSearch and records a warning
  2. JPMorgan Chase jobs from `jpmc.fa.oraclecloud.com` appear in the pipeline output
  3. CSX, Florida Blue, and Availity ATS platforms are documented; any that use a supported ATS have a working fetcher wired in
  4. A fetcher that fails once is retried exactly once before being marked failed; other fetchers continue uninterrupted
  5. A fetcher that hangs is cancelled after 120 seconds and counted as failed
  6. The GitHub Actions workflow file contains the correct UTC cron offsets for both EDT and EST with a comment noting the next DST adjustment date
**Plans**: 7 plans

Plans:
- [ ] 02-01-PLAN.md — FetcherFailure TypedDict and all test scaffolds in red state (Wave 0)
- [ ] 02-02-PLAN.md — _run_fetcher retry, _fetch_jobs 3-tuple, build_fetchers warnings (Wave 1)
- [ ] 02-03-PLAN.md — JSearchFetcher implementation (Wave 1, parallel)
- [ ] 02-04-PLAN.md — OracleFetcher implementation (Wave 1, parallel)
- [ ] 02-05-PLAN.md — JPMC, CSX, Florida Blue, Availity wired in + ats_research.md (Wave 2)
- [ ] 02-06-PLAN.md — Detail-page timeout standardization to 12s + 120s batch cap (Wave 1, parallel)
- [ ] 02-07-PLAN.md — GitHub Actions cron DST update + JSEARCH_API_KEY env (Wave 1, parallel)

### Phase 3: Feedback Loop
**Goal**: Users can vote on job relevance from email, votes are persisted reliably, old votes are archived, and feedback biases scoring
**Depends on**: Phase 1 (FEED-04 requires SCORE-04)
**Requirements**: FEED-01, FEED-02, FEED-03, FEED-04
**Success Criteria** (what must be TRUE):
  1. Each qualified job card in the email contains working thumbs-up and thumbs-down links that open the GitHub Pages feedback UI with the correct job ID and vote direction
  2. Clicking a vote link triggers `feedback.yml`, appends a complete vote record to `feedback.json`, and commits the file
  3. On each pipeline run, votes older than 90 days are moved to the correct `feedback_archive_YYYY_MM.json` file and removed from active `feedback.json`
  4. Jobs matching tokens with sufficient feedback votes score higher or lower than equivalent jobs without feedback signal, as confirmed by `jobs_debug.json` score breakdown
**Plans**: TBD

### Phase 4: Email Enhancements
**Goal**: The email digest is always delivered with sorted results, full pipeline health visibility, and a feedback-informed weekly summary
**Depends on**: Phase 2 (EMAIL-03 needs FETCH-04 retry data), Phase 3 (EMAIL-07 needs feedback.json populated)
**Requirements**: EMAIL-01, EMAIL-02, EMAIL-03, EMAIL-04, EMAIL-05, EMAIL-06, EMAIL-07, EMAIL-08
**Success Criteria** (what must be TRUE):
  1. Qualified jobs in the email appear in descending score order; the highest-scoring job is always first
  2. An email is sent on every run, even when zero jobs qualify — showing the "No new qualified jobs this run" message
  3. Any fetcher that failed after retry appears in a prominently placed Failed Fetchers section of the email
  4. Jobs that scored below threshold but match the title passlist appear in a "Possibly Relevant" section separate from qualified jobs
  5. `jobs_debug.json` is committed to the repo after every GitHub Actions run
  6. The email Run Summary shows fetched count, duplicates, filtered, scored-out, qualified, per-fetcher status, and one-line warnings for any unconfigured optional keys
  7. On the first Monday run with 20+ feedback votes, the email includes a Weekly Pattern Summary with thumbs-down patterns and suggested blocklist additions
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in order: 1 → 2 → 3 → 4 (Phase 1 and Phase 2 can run in parallel on separate branches)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Scoring & Profile | 3/5 | In Progress|  |
| 2. Fetchers | 0/7 | Planned | - |
| 3. Feedback Loop | 0/TBD | Not started | - |
| 4. Email Enhancements | 0/TBD | Not started | - |
