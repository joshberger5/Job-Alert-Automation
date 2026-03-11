# Requirements — Job Alert Automation

## v1 Requirements

### Scoring & Profile (SCORE)

- [x] **SCORE-01**: User's candidate preferences (preferred_locations, remote_allowed, open_to_contract, minimum_salary, feedback reason tags) are loaded from `candidate_profile.yaml` in the project root, not hardcoded in source code
- [x] **SCORE-02**: Jobs with a parseable `salary_max` below `minimum_salary` are filtered out; jobs with no salary listed always pass
- [x] **SCORE-03**: Tertiary skills extracted from the resume's Experience and Projects sections are validated against a curated tech taxonomy before being used in scoring — noisy tokens (non-tech abbreviations, single-occurrence tokens) are excluded
- [x] **SCORE-04**: After base skill scoring, a personal bias adjustment is applied using `feedback.json` vote history — tokens with ≥ 3 net votes influence the score via `FEEDBACK_WEIGHT = 0.5`; tokens below threshold are ignored
- [x] **SCORE-05**: Experience gap thresholds match DESIGN.md spec: `required ≤ ideal_max` → WITHIN_IDEAL_RANGE (pass); `required ≤ ideal_max + 4` → MODERATE_GAP (filtered); `required > ideal_max + 4` → LARGE_GAP (filtered)

### Fetchers (FETCH)

- [ ] **FETCH-01**: JSearch fetcher runs two queries (local: "java developer Jacksonville FL", remote: "java developer remote", 3-day window); fetcher is skipped entirely with a warning in the email if `JSEARCH_API_KEY` is not set
- [ ] **FETCH-02**: OracleFetcher class implemented for JPMorgan Chase (`jpmc.fa.oraclecloud.com`) and wired into the fetcher pool in `main.py`
- [ ] **FETCH-03**: ATS platforms verified for CSX, Florida Blue, and Availity (careers page inspection); fetchers implemented for any that use a supported ATS (Greenhouse, Lever, Workday, iCIMS)
- [ ] **FETCH-04**: Every fetcher gets exactly 1 retry on failure before being marked as failed; failed fetchers are reported in the email and do not block the rest of the run
- [ ] **FETCH-05**: Each fetcher in the ThreadPoolExecutor has a 120-second wall-clock timeout; hung fetchers are skipped and counted as failed
- [ ] **FETCH-06**: Detail-page HTTP timeout is 12 seconds across all fetchers that fetch individual job pages (Workday, iCIMS, AdzunaSimilar)
- [ ] **FETCH-07**: GitHub Actions workflow cron schedule has correct UTC offsets for EDT (`0 10,16,21 * * *`) and EST (`0 11,17,22 * * *`) with a comment noting the next DST adjustment date

### Email (EMAIL)

- [ ] **EMAIL-01**: Qualified jobs in the email digest are sorted by score descending (highest score first)
- [ ] **EMAIL-02**: Email is always sent every run, even when there are zero qualified jobs — shows a "No new qualified jobs this run" message instead of being suppressed
- [ ] **EMAIL-03**: Email includes a Failed Fetchers section listing any fetcher that failed after retry, shown prominently (not buried in run summary)
- [ ] **EMAIL-04**: Email includes a "Possibly Relevant" section listing scored-out jobs whose title matches any of: software engineer, developer, backend, full stack, java, platform engineer, devops, sre, mobile engineer, qa automation; `llm_relevant=True` jobs also appear here when Gemini is enabled
- [ ] **EMAIL-05**: `jobs_debug.json` is committed to the repo after every GitHub Actions run via `git add -f` (bypassing .gitignore)
- [ ] **EMAIL-06**: Email includes a Run Summary section showing: total fetched, duplicates skipped, filtered out, scored out, qualified, and per-fetcher status (success/failed)
- [ ] **EMAIL-07**: On the first run of each Monday, if `feedback.json` contains ≥ 20 total votes, email includes a Weekly Pattern Summary analyzing thumbs-down patterns and suggesting keyword blocklist additions
- [ ] **EMAIL-08**: Run Summary includes one-line warnings for each optional integration that is not configured (`JSEARCH_API_KEY`, `GEMINI_API_KEY`)

### Feedback (FEED)

- [ ] **FEED-01**: Each qualified job card in the email contains 👍 and 👎 URL links pointing to the GitHub Pages feedback UI with job ID and vote direction as query parameters
- [ ] **FEED-02**: `feedback.yml` GitHub Actions workflow receives `repository_dispatch` events from the feedback UI, appends the vote (job_id, title, company, vote, reason, voted_at) to `feedback.json`, and commits
- [ ] **FEED-03**: On each run, votes older than 90 days are moved from `feedback.json` to `feedback_archive_YYYY_MM.json` (one file per calendar month) and committed
- [ ] **FEED-04**: Feedback bias scoring (SCORE-04) is wired into `ScoringPolicy` using data loaded by `FeedbackService` at startup

## v2 (Deferred)

- Secondary dedup key for Fanatics (title+company hash) — dedup by job ID handles most cases for now
- Gemini-assisted tertiary skill classification — taxonomy-only is sufficient for v1
- Geographic radius / commute logic — substring location matching is acceptable for now
- Title normalization before LLM filter — "Sr." vs "Senior" inconsistency is low priority
- No-retry on feedback webhook error — visible error message on feedback page deferred

## Out of Scope

- Multi-user support — single developer, always
- Web dashboard — email is the delivery mechanism; GitHub Pages is feedback input only
- Paid job board APIs beyond JSearch — no budget
- ATS types beyond Greenhouse, Lever, Workday, iCIMS, Ceridian, Oracle, and direct scraping
- LLM batching/chunking for Gemini — single-call approach is acceptable at current scale

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SCORE-01 | Phase 1 | Complete |
| SCORE-02 | Phase 1 | Complete |
| SCORE-03 | Phase 1 | Complete |
| SCORE-04 | Phase 1 | Complete |
| SCORE-05 | Phase 1 | Complete |
| FETCH-01 | Phase 2 | Pending |
| FETCH-02 | Phase 2 | Pending |
| FETCH-03 | Phase 2 | Pending |
| FETCH-04 | Phase 2 | Pending |
| FETCH-05 | Phase 2 | Pending |
| FETCH-06 | Phase 2 | Pending |
| FETCH-07 | Phase 2 | Pending |
| FEED-01 | Phase 3 | Pending |
| FEED-02 | Phase 3 | Pending |
| FEED-03 | Phase 3 | Pending |
| FEED-04 | Phase 3 | Pending |
| EMAIL-01 | Phase 4 | Pending |
| EMAIL-02 | Phase 4 | Pending |
| EMAIL-03 | Phase 4 | Pending |
| EMAIL-04 | Phase 4 | Pending |
| EMAIL-05 | Phase 4 | Pending |
| EMAIL-06 | Phase 4 | Pending |
| EMAIL-07 | Phase 4 | Pending |
| EMAIL-08 | Phase 4 | Pending |
