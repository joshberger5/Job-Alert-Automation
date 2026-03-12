# Job Alert Automation

## What This Is

A personal Python automation that runs 3× daily via GitHub Actions. It fetches job postings from 20+ company career pages and job boards, scores each against the user's resume (extracted from `resume.tex`), and emails a digest of qualified matches. Built and used by a single developer actively job-searching in the Jacksonville, FL area or remote.

## Core Value

Surface relevant job postings from every configured source, filtered and scored against the user's actual skills, before the jobs go stale — with zero manual effort.

## Requirements

### Validated

- ✓ Multi-source job fetching via ThreadPoolExecutor (Adzuna, Greenhouse, Lever, Workday, RemoteOK, WeWorkRemotely, BankOfAmerica, iCIMS, iCIMS Sitemap, Landstar, AdzunaSimilar) — existing
- ✓ Resume skill extraction from resume.tex (core/secondary/tertiary with weights 4/2/1) — existing
- ✓ Experience gap filtering (scans job content for year requirements, compares to candidate's total experience) — existing
- ✓ Remote and location filtering (preferred_locations substring match, remote phrase detection) — existing
- ✓ Employment type filtering (contract, internship, part_time blocked) — existing
- ✓ Deduplication via seen_jobs.json (permanent, never expires) — existing
- ✓ HTML email digest (job cards with score badge, salary, link) — existing
- ✓ Keyword title blocklist filter (data scientist, product manager, recruiter, etc.) — existing
- ✓ Optional Gemini LLM title filter (gemini-2.0-flash-lite, fails open) — existing
- ✓ GitHub Actions scheduled execution (3×/day at 6 AM, 12 PM, 5 PM ET) — existing
- ✓ jobs_debug.json output with full score breakdown per job — existing
- ✓ Salary parsing via SalaryParser shared helper — existing
- ✓ Feedback system scaffolding (FeedbackService, FeedbackRepository, feedback.json, GitHub Pages UI, repository_dispatch workflow) — existing
- ✓ **SCORE-01**: Candidate preferences in `candidate_profile.yaml` (minimum_salary: 85000, reason tags, preferred_locations, remote_allowed, open_to_contract) — Phase 1
- ✓ **SCORE-02**: Salary floor filter in `FilteringPolicy.allows()` — rejects jobs where `salary_max < minimum_salary`; fail-open on missing salary — Phase 1
- ✓ **SCORE-03**: Tertiary skill extraction with Counter frequency filter (≥2 occurrences), taxonomy gate (`tech_taxonomy.yaml`, 61 tokens), optional Gemini classification with cache — Phase 1
- ✓ **SCORE-04**: `FeedbackBiasService` with vote-history multiplier (`FEEDBACK_WEIGHT=0.5`, min 3 net votes), clamped to [0.5, 2.0], wired into `JobProcessingService`; `feedback_multiplier` in `jobs_debug.json` — Phase 1
- ✓ **SCORE-05**: Experience gap thresholds corrected (MODERATE: `required ≤ ideal_max + 4`; LARGE: `required > ideal_max + 4`) — Phase 1
- [ ] **FETCH-01**: Implement JSearchFetcher (local + remote queries, 3-day window, optional — skip with email warning if `JSEARCH_API_KEY` not set)
- [ ] **FETCH-02**: Implement OracleFetcher for JPMorgan Chase (`jpmc.fa.oraclecloud.com`)
- [ ] **FETCH-03**: Verify ATS platforms for CSX, Florida Blue, Availity; implement fetchers where feasible
- [ ] **FETCH-04**: Add retry logic — 1 retry per fetcher before marking as failed
- [ ] **FETCH-05**: Add 120s wall-clock timeout per fetcher in ThreadPoolExecutor
- [ ] **FETCH-06**: Standardize detail-page HTTP timeout to 12s across all fetchers (Workday, iCIMS, AdzunaSimilar)
- [ ] **FETCH-07**: Update DST cron schedule comment and set correct UTC offsets (EDT: `0 10,16,21 * * *`; EST: `0 11,17,22 * * *`)
- [ ] **EMAIL-01**: Sort qualified jobs by score descending in email
- [ ] **EMAIL-02**: Always send email even when no qualified jobs (show "No new qualified jobs this run")
- [ ] **EMAIL-03**: Add failed fetcher section to email (shown prominently when any fetcher fails after retry)
- [ ] **EMAIL-04**: Add "Possibly Relevant" section — scored-out jobs matching a title passlist (software engineer, developer, backend, full stack, java, platform engineer, devops, sre, qa automation)
- [ ] **EMAIL-05**: Commit `jobs_debug.json` to repo after each run via `git add -f`
- [ ] **EMAIL-06**: Add Run Summary section (fetched count, duplicates, filtered, scored-out, qualified, fetcher status)
- [ ] **EMAIL-07**: Add Weekly Pattern Summary — shown on first Monday run when `feedback.json` has ≥ 20 votes; surfaces thumbs-down patterns, suggests blocklist additions
- [ ] **EMAIL-08**: Add missing optional key warnings in Run Summary (JSearch, Gemini)
- [ ] **FEED-01**: Wire feedback vote buttons (plain URL links) in job cards linking to GitHub Pages UI
- [ ] **FEED-02**: Ensure `feedback.yml` GitHub Actions workflow receives repository_dispatch, appends vote to `feedback.json`, commits
- [ ] **FEED-03**: Implement feedback archival — votes > 90 days → `feedback_archive_YYYY_MM.json`, remove from active `feedback.json`
- [ ] **FEED-04**: Integrate feedback bias map into scoring (prerequisite: SCORE-04)

### Out of Scope

- Multi-user support — single developer, single resume, always
- Web dashboard — email is the delivery mechanism; GitHub Pages is only for feedback input
- Real-time notifications — scheduled 3×/day is sufficient
- Paid job board APIs beyond JSearch (RapidAPI) — no budget for premium APIs
- ATS types beyond Greenhouse, Lever, Workday, iCIMS, Ceridian, Oracle, and custom scraping

## Context

- **Architecture**: Domain-Driven Design — `domain/` (pure logic), `application/` (orchestration), `infrastructure/` (I/O), `main.py` (wiring only)
- **Tech stack**: Python, pytest, mypy (strict), GitHub Actions, SMTP email, GitHub Pages
- **Branch strategy**: 4 parallel feature branches (`feature/scoring`, `feature/fetchers`, `feature/email`, `feature/feedback`) — never commit directly to `main`
- **Key constraint**: `py` alias only (Windows). `python`/`python3` not aliased locally; use `python` only in GitHub Actions YAML.
- **DESIGN.md** is the authoritative spec for all business logic, thresholds, and implementation decisions

## Constraints

- **Tech stack**: Python only — no Node.js, no new languages
- **Branching**: All work on feature branches — developer handles merges after review
- **File deletion**: Move to `/trash/` instead of deleting permanently
- **Tests + mypy**: Must pass after every change before committing
- **Commit frequency**: Commit after every meaningful unit of work (function, test, config change)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| candidate_profile.yaml for preferences | Avoid hardcoding personal config in source code | ✓ Done — Phase 1 |
| FEEDBACK_WEIGHT = 0.5, min signal = 3 votes | Prevent single vote from distorting scores | ✓ Done — Phase 1 |
| `_ProfileConfig(TypedDict, total=False)` | Allows config.get() with defaults for optional YAML keys | ✓ Done — Phase 1 |
| Salary filter uses explicit `maximum is not None` check | Preserve fail-open on missing salary (not `meets_minimum()`) | ✓ Done — Phase 1 |
| `Counter` for token collection in tertiary extraction | Enables O(n) frequency filtering over set-based approach | ✓ Done — Phase 1 |
| `FeedbackBiasService.apply()` returns 3-tuple | Single call returns (final_score, breakdown, multiplier) | ✓ Done — Phase 1 |
| Fails-open on LLM filter errors | Never silently drop jobs due to API errors | ✓ Good |
| DDD layering (domain/application/infrastructure) | Keeps business logic testable without I/O | ✓ Good |
| seen_jobs.json never expires | Simple, predictable dedup — delete file to reset | ✓ Good |
| Fanatics on both Lever + Greenhouse | They post on both; dedup by job ID handles most overlap | ⚠️ Revisit |

---
*Last updated: 2026-03-11 after Phase 1*
