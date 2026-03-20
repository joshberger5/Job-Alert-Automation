# Job Alert Automation

Scrapes job postings from 27 sources (up to 29 with optional JSearch) 3× daily, scores them against a candidate profile parsed from a LaTeX resume, filters titles with a fast keyword list and an optional Gemini LLM pass, and emails a formatted digest of qualified matches. Each email card contains thumbs-up/thumbs-down vote links; votes accumulate in a 50-record ring buffer and bias future scoring via `FeedbackBiasService`. After each successful run, `improve_rules.yml` runs Claude Code non-interactively to analyze `jobs_debug.json` and open a PR with targeted filter improvements if any are found.

![Email preview](docs/email_preview_cropped.png)

---

## Setup

```bash
pip install -r requirements.txt
```

**`.env`** (required):
```
ADZUNA_APP_ID=...
ADZUNA_APP_KEY=...

# Optional — email is skipped if SMTP_HOST is absent
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASS="app password"
EMAIL_TO=you@example.com

# Optional — enables LLM title filtering (Gemini free tier)
GEMINI_API_KEY=...

# Optional — enables JSearch/RapidAPI fetcher (2 additional sources)
JSEARCH_API_KEY=...

# Optional — enables thumbs-up/thumbs-down vote links in email cards
FEEDBACK_PAT=...
```

Place `resume.tex` in the project root. Edit `candidate_profile.yaml` to set your preferences:

```yaml
preferred_locations:
  - Jacksonville
  - Jacksonville Beach
remote_allowed: true
open_to_contract: false
minimum_salary: 85000          # 0 = no salary filter
feedback_thumbs_down_reasons:  # reason tags used in the feedback UI
  - Too senior
  - Too junior
  - Wrong tech stack
  - Bad company
  - Contract/not permanent
  - Wrong location
  - Not relevant title
feedback_thumbs_up_reasons:
  - Great tech stack
  - Right level
  - Good company
  - Interesting domain
  - Great pay
```

Then:

```bash
py main.py
```

---

## How It Works

### 1 — Profile Extraction

`LatexResumeParser` strips LaTeX markup from `resume.tex` to produce plain text. `ResumeProfileBuilder` then constructs a `CandidateProfile` by:

- Locating the **Technical Skills** section and splitting it into categories. The first category (e.g. Languages) becomes `core_skills` with weight **4**; all remaining categories become `secondary_skills` with weight **2**.
- Scanning the **Experience** and **Projects** sections for capitalized tokens, then applying two filters: (1) **frequency gate** — tokens appearing only once are dropped; (2) **taxonomy gate** — tokens are checked against `infrastructure/tech_taxonomy.yaml` (61 curated tech terms). Taxonomy hits are always included. Unknown tokens are optionally classified by Gemini (when `GEMINI_API_KEY` is set) and cached in `infrastructure/tertiary_cache.json`; without a key, unknown tokens are kept (fail-open). Survivors become `tertiary_skills` with weight **1**. Generic terms already covered by higher-tier skills (e.g. `rest`, `api` when `rest apis` is already secondary) are excluded via a stop-word list.
- Calculating `ideal_max_experience_years` by summing date-range durations found in the **Experience** section (total months ÷ 12, rounded down).
- Loading all preferences from `candidate_profile.yaml`: `preferred_locations`, `remote_allowed`, `open_to_contract`, `minimum_salary`, `feedback_thumbs_down_reasons`, `feedback_thumbs_up_reasons`.

### 2 — Fetching

All fetchers implement the `JobFetcher` protocol (`fetch() -> list[Job]`) and run **concurrently** via `ThreadPoolExecutor`. Each has a 120-second wall-clock timeout; a hung fetcher is skipped without blocking the rest. Each fetcher is attempted up to **2 times** before being recorded as a `FetcherFailure` and skipped. Fetcher wiring lives in `infrastructure/fetcher_registry.py`.

| Source | Class | API Mechanism |
|---|---|---|
| Adzuna (local) | `AdzunaFetcher` | REST JSON — paginated, filters by keyword + location |
| Adzuna (remote, national) | `AdzunaFetcher` | Same API, `keywords="java remote"`, no location constraint, 3-day window |
| Adzuna (similar) | `AdzunaSimilarFetcher` | Collects seed job URLs from Adzuna, then scrapes the "Similar jobs" section from each detail page in parallel; deduplicates by job ID |
| RemoteOK | `RemoteOKFetcher` | `remoteok.com/api?tags=java` — single JSON array, all results remote |
| We Work Remotely | `WeWorkRemotelyFetcher` | RSS XML feed — programming category; skips explicitly non-USA regions |
| SoFi, Robinhood, Brex, Coinbase, DoorDash, Gusto, Checkr | `GreenhouseFetcher` | `boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true` — single request, all jobs |
| Dun & Bradstreet | `LeverFetcher` | `api.lever.co/v0/postings/{company}?mode=json` |
| Allstate | `WorkdayFetcher` | POST `allstate.wd5.myworkdayjobs.com/…/jobs` — descriptions fetched via ld+json, **parallelized** |
| GEICO | `WorkdayFetcher` | POST `geico.wd1.myworkdayjobs.com/…/jobs` — descriptions fetched via ld+json, **parallelized** |
| FIS Global | `WorkdayFetcher` | POST `/wday/cxs/fis/SearchJobs/jobs` — paginated JSON |
| SSC Technologies | `WorkdayFetcher` | POST `/wday/cxs/ssctech/SSCTechnologies/jobs` — descriptions fetched from job pages via ld+json, **parallelized** |
| VyStar Credit Union | `WorkdayFetcher` | Same as above |
| Availity | `WorkdayFetcher` | POST `availity.wd1.myworkdayjobs.com/…/jobs` — descriptions fetched via ld+json, **parallelized** |
| Landstar System | `LandstarFetcher` | POST `jobs.dayforcehcm.com/api/geo/landstar/jobposting/search` (Ceridian Dayforce) — paginated JSON; salary extracted from description text |
| Bank of America (×2) | `BankOfAmericaFetcher` | `/services/jobssearchservlet` — one instance location-only, one with `keywords=Java`; deduplication handles overlap |
| Paysafe | `IcimsFetcher` | HTML scrape of `/tile-search-results/` (paginated, capped at 300 jobs); detail page per job, **parallelized** |
| FNF | `IcimsSitemapFetcher` | Parses `sitemap.xml` for job URLs, fetches `?in_iframe=1` on each to read ld+json, **parallelized** |
| JPMorgan Chase, CSX, Florida Blue | `OracleFetcher` | Oracle Cloud HCM ICE REST endpoint (`/hcmRestApi/resources/…/recruitingICEJobRequisitions`); detail page per job for description, **parallelized** |
| JSearch (local + remote) | `JSearchFetcher` | RapidAPI JSearch endpoint — **optional**, only wired when `JSEARCH_API_KEY` is set; 3-day recency window |

Detail-page fetches inside `WorkdayFetcher`, `IcimsFetcher`, `IcimsSitemapFetcher`, and `OracleFetcher` use `ThreadPoolExecutor(max_workers=10)` with a **12-second** per-request timeout and a **120-second** batch cap.

### 3 — Keyword Title Filtering

`KeywordTitleFilter` (`infrastructure/keyword_title_filter.py`) runs before policy filtering so obvious non-fits never reach the more expensive downstream steps. It uses case-insensitive substring matching on the job title with a three-tier priority:

1. **Hard reject** (seniority-based; whitelist cannot override) — fragments like `"staff software"` and `"principal software"` that indicate a level structurally out of range regardless of role type.
2. **Whitelist** (overrides role-type rejections) — fragments like `"software engineer, backend"` and `"backend software engineer"` that unambiguously identify a target role and protect it from future over-aggressive role-type reject rules.
3. **Role-type reject** — fragments for clearly wrong role categories: data scientist, product manager, site reliability engineer, solutions engineer, data analyst, test infrastructure, manual QA, recruiter, etc.

### 4 — Policy Filtering

`FilteringPolicy.allows()` evaluates each job in order; first failing check eliminates the job:

1. **Contract filter** — rejected if `employment_type == "contract"` and `open_to_contract` is False.
2. **Salary floor filter** — if `minimum_salary > 0`, rejected when `salary_max` is known and below the floor. Jobs with no salary listed always pass (fail-open on missing data).
3. **Experience gap filter** — `ExperienceRequirement.from_job_content()` tokenizes `"{title} {description}"` and finds the first number followed by a year token (`year`, `years`, `yrs`) within an 8-token window of the word `experience`. Handles `"15+"`, `"5-10 years"`, `"years,"`, `"years'"` etc. via leading-digit regex and punctuation stripping. Classified against `ideal_max_experience_years`:
   - `≤ max` → `WITHIN_IDEAL_RANGE` (pass)
   - `≤ max + 4` → `MODERATE_GAP` (reject)
   - `> max + 4` → `LARGE_GAP` (reject)
   - Not found → `UNKNOWN` (pass — benefit of the doubt)
4. **Remote check** — passes if:
   - `job.remote is True` **and** the location is US-accessible (strips "remote", checks remaining words against `{"us", "usa", "united", "states", "america", "worldwide", "global", "anywhere"}`; empty location passes), **or**
   - `job.remote is None` **and** the description/location contains an explicit remote phrase (`"fully remote"`, `"100% remote"`, `"work from home"`, etc.) **and** the location is US-accessible (prevents foreign on-site jobs from slipping through via description phrasing).
5. **Location check** — passes if any `preferred_locations` substring appears in `job.location` (case-insensitive).

### 5 — Scoring

`ScoringPolicy.evaluate()` operates on `"{title} {description}".lower()`:

- **+weight** for each skill found in content (`core_skills` weight 4, `secondary_skills` weight 2, `tertiary_skills` weight 1).
- **−2** for each skill in `job.required_skills` not present in the candidate's combined skill set (only applies when the fetcher populates `required_skills`; most don't — `RemoteOKFetcher` does via job tags).
- **Qualifies** if `score ≥ 7` (`ScoringPolicy.MINIMUM_SCORE`).

After scoring, `FeedbackBiasService` applies a personal multiplier derived from feedback vote history (`feedback.json`). Each vote record stores a `reasons[]` array; every token in the array independently accumulates net votes. Reason tokens with ≥ 3 net votes contribute `net_votes × 0.5` to the multiplier, clamped to `[0.5, 2.0]`. The adjusted score determines `"qualified"` or `"scored_out"`, and `feedback_multiplier` is written to `jobs_debug.json`.

### 6 — LLM Title Filtering (optional)

When `GEMINI_API_KEY` is set, `GeminiTitleFilter` runs a single batch call to `gemini-2.0-flash-lite` (free tier) on all post-filter records (`"qualified"` + `"scored_out"`). The prompt is built from `profile.core_skills` and `profile.ideal_max_experience_years` and asks the model to identify which job titles are genuine software engineering roles for the candidate.

- **Qualified jobs the LLM rejects** are re-marked `"llm_filtered"` and excluded from the email's main section (but still shown in a secondary section).
- **Scored-out jobs the LLM approves** get `llm_relevant=True` added to their debug record and appear in a third email section.
- **Fails open** — any API error returns all IDs, so no jobs are silently dropped.

### 7 — Persistence

`JsonJobRepository` loads `seen_jobs.json` on startup and writes it after every `save()` call. Records are never expired — delete the file to reset. Schema:

```json
{
  "job_id": { "first_seen": "2026-03-01T09:00:00", "score": 12, "qualified": true }
}
```

Duplicate detection happens before filtering and scoring, so already-seen jobs cost only a dict lookup.

### 8 — Events & Debug Output

`JobProcessingService` emits `JobEvaluated` and `JobQualified` domain events via `InMemoryEventPublisher` → `SimpleEventDispatcher`. Each job's result is recorded in `jobs_debug.json` with full score breakdown, filter reason, and metadata. `jobs_debug.json` and `resume.tex` are committed to the repo after every CI run so they're always available for analysis. The `result` field is one of:

| Value | Meaning |
|---|---|
| `"duplicate"` | Already seen in a previous run — skipped immediately |
| `"filtered_out"` | Failed `FilteringPolicy` (contract, experience gap, or location) |
| `"scored_out"` | Passed filtering but `score < MINIMUM_SCORE` |
| `"qualified"` | Passed filtering and scoring |
| `"llm_filtered"` | Passed scoring but LLM flagged the title as irrelevant |

### 9 — Email

`EmailNotifier.send()` builds an HTML email (table-based, inline styles for client compatibility) with up to three sections:

- **Qualified jobs** — always present when any exist. One card per job: company, title, location, employment type, salary (if known), score badge (green ≥ 14, blue ≥ 10, amber ≥ 7), "View Job →" link, and thumbs-up/thumbs-down vote links (shown only when `FEEDBACK_PAT` is set). Cards are ordered by score descending within each section.
- **LLM Rejected** — jobs that scored high enough but were flagged by the LLM title filter. Shown only when `GEMINI_API_KEY` is set and at least one job was re-classified. Ordered by score descending.
- **Possibly Relevant** — scored-out jobs that the LLM considers worth a look. Shown only when `GEMINI_API_KEY` is set and any such jobs exist. Ordered by score descending.

Sent via SMTP STARTTLS. Skipped entirely if `SMTP_HOST` is not set.

### 10 — Feedback Loop

When `FEEDBACK_PAT` is set, each qualified job card in the email contains 👍 and 👎 vote links. Clicking one opens `docs/feedback.html` (GitHub Pages), where the user selects a reason tag and submits. The page fires a `repository_dispatch` event to GitHub, which triggers `feedback.yml`.

**`feedback.yml` workflow** (`.github/workflows/feedback.yml`):
1. Reads the vote payload from `github.event.client_payload`
2. Appends a record to `feedback.json`, sorts by `voted_at`, and trims to the **50 most recent** records (`_trim_votes()` in `infrastructure/feedback_trimmer.py` mirrors this logic for unit tests)
3. Reads `candidate_profile.yaml` and injects the reason arrays into `docs/feedback.html` (replacing `__THUMBS_UP_REASONS__` and `__THUMBS_DOWN_REASONS__` placeholders)
4. Commits both files with `[skip ci]` to avoid triggering `job_alerts.yml`

**`feedback.json` schema** (each record):
```json
{ "job_id": "...", "vote": 1, "title": "...", "company": "...", "reasons": ["Great tech stack"], "voted_at": "2026-03-16T12:00:00" }
```

`vote` is `1` (thumbs-up) or `-1` (thumbs-down). `reasons` is a non-empty array. The file holds at most 50 records; resetting history requires deleting it.

The PAT is passed in the URL **fragment** (`#token`), not the query string, to keep it out of server logs. It requires `Contents: read/write` permission on the repo (fine-grained token) to commit `feedback.json`.

---

## Tests

```bash
# Unit tests (no network calls)
py -m pytest tests/ -v --ignore=tests/e2e/

# E2E fetcher health checks (real HTTP — requires .env with Adzuna keys)
py -m pytest tests/e2e/ -v
```

198 unit tests across 26 files, all passing with no network calls (all HTTP is mocked via `unittest.mock.patch`).

### E2E fetcher health checks

`tests/e2e/test_fetcher_health.py` runs one parametrized test per fetcher against live endpoints. A `FAILED` result means the fetcher raised an exception (SSL error, 401, timeout, etc.). Zero jobs returned is a valid pass — it just means no open roles matched today.

- **Locally without `.env`**: 0 tests collected (skipped gracefully)
- **Locally with `.env`**: all fetchers exercised; known broken ones (BofA ×2, JPMorgan Chase, CSX, Florida Blue) will show `FAILED`
- **GitHub Actions**: runs as a separate `E2E fetcher health check` step with `continue-on-error: true` — failures are visible in the step log but never block the workflow

The `e2e` pytest marker is registered in `pytest.ini`.

| File | Tests | What it covers |
|---|---|---|
| `test_adzuna_fetcher.py` | 7 | Field mapping, salary variants (min-only, max-only, absent), remote detection, pagination, single-page stop |
| `test_greenhouse_fetcher.py` | 3 | HTML stripping from `content`, remote detection, missing/null location |
| `test_lever_fetcher.py` | 4 | Salary formatting, `location` passed as query param, employment type variants (`contract`, `part-time`, `internship`) |
| `test_workday_fetcher.py` | 4 | Field mapping with `fetch_descriptions=False`, pagination, remote detection, ld+json extraction with `fetch_descriptions=True` |
| `test_boa_fetcher.py` | 3 | Field mapping (`family \| lob` description, URL construction), pagination, missing `jcrURL` → `url=None` |
| `test_remoteok_fetcher.py` | 3 | Metadata element skipped, `location: null` → `"Worldwide"`, `tags: null` → `required_skills=[]` |
| `test_weworkremotely_fetcher.py` | 4 | Region filtering (`"Europe Only"` skipped), no-colon title fallback, HTML description stripping |
| `test_job_processing_service.py` | 17 | All four result paths (duplicate, filtered_out, scored_out, qualified); correct `repo.save` args per path; `JobEvaluated` + `JobQualified` events on qualified; `feedback_multiplier` on scored records; mixed-batch ordering |
| `test_scoring_policy.py` | 9 | Word-boundary skill matching (Java ≠ JavaScript, C ≠ account), missing-skill penalties, `qualifies()` at/above/below threshold |
| `test_experience_requirement.py` | 12 | Year-phrase parsing (trailing punctuation, `+` suffix, range), `UNKNOWN` when absent, gap classification (`WITHIN_IDEAL_RANGE`, `MODERATE_GAP`, `LARGE_GAP`), boundary cases at `ideal_max+4` and `ideal_max+5` |
| `test_keyword_title_filter.py` | 14 | Role-type rejection fragments (data scientist, product manager, solutions engineer, test infrastructure, etc.), seniority hard-reject (staff software), whitelist overrides role-type reject, whitelist does not override hard reject, case-insensitivity, custom fragment injection |
| `test_filtering_policy.py` | 15 | Contract filter, salary floor (below/above/missing/disabled), experience gap filter, remote=True/None/Europe logic, preferred-location substring match |
| `test_landstar_fetcher.py` | 19 | Field mapping, salary (annual + hourly→annual conversion, absent), remote detection (`hasVirtualLocation`, title, description), multi-location formatting, pagination, error handling |
| `test_adzuna_similar_fetcher.py` | 10 | Job extraction from "Similar jobs" section, ID/salary/URL parsing, cross-seed deduplication, graceful degradation on HTTP errors and missing section |
| `test_resume_profile_builder.py` | 10 | `minimum_salary` and reason tags loaded from YAML; taxonomy-gated tertiary extraction (single-occurrence excluded, taxonomy hit included, fail-open when no Gemini key); bare numbers excluded; `api`/`rest` excluded as stop words |
| `test_feedback_bias_service.py` | 10 | No-file → multiplier 1.0; below-threshold token skipped; at-threshold token applied; min/max clamp (0.5/2.0); score delta in breakdown; multi-reason independent accumulation |
| `test_oracle_fetcher.py` | 3 | Field mapping from ICE REST response, detail-page description extraction, pagination |
| `test_jsearch_fetcher.py` | 3 | Field mapping, `job_is_remote` handling, salary formatting |
| `test_fetcher_result.py` | 2 | `FetcherFailure` TypedDict field presence and types |
| `test_main_retry.py` | 4 | `_run_fetcher` succeeds on first attempt, retries once on failure, records failure after 2 attempts |
| `test_detail_timeout.py` | 3 | `_DETAIL_TIMEOUT == 12` in `WorkdayFetcher`, `IcimsFetcher`, `AdzunaSimilarFetcher` |
| `test_email_notifier.py` | 13 | Run Log rendering, HTML escaping, score-descending ordering in all three email sections, input list not mutated; vote links present/absent/URL-structured |
| `test_email_archiver.py` | 6 | Directory creation, correct filename and content, oldest-file trimming when over max, PAT redaction in archived HTML |
| `test_feedback_json_trim.py` | 3 | `_trim_votes()` keeps last 50, no-op under 50, sorts by `voted_at` before trimming |
| `test_tee.py` | 6 | `Tee` write/flush forwarding to primary and secondary streams |
| `test_main_timeout.py` | 2 | `_fetch_jobs` returns 3-tuple; timed-out fetcher recorded as failure |

Fixtures (JSON, HTML, RSS) live in `tests/fixtures/` — either trimmed real API responses or synthetic data matching the exact schema each fetcher expects.

---

## Mutation Testing

[mutmut](https://mutmut.readthedocs.io/) is the Python equivalent of pitest — it introduces small code mutations (flipping `+` to `-`, changing `True` to `False`, etc.) one at a time and runs the test suite against each. A mutation that isn't caught by any test is a **survived mutant**, which reveals a gap in test coverage. Results are browsable as an HTML report.

Mutation testing targets `domain/` and `application/` only (configured in `setup.cfg`). `infrastructure/` is excluded because fetcher I/O is heavily mocked and produces little signal.

```bash
# Install (included in requirements.txt)
pip install -r requirements.txt

# Run all mutations (takes several minutes — run locally, not in CI)
py -m mutmut run

# Print a terminal summary
py -m mutmut results

# Generate an HTML report (analogous to pitest's HTML output)
py -m mutmut html
# → opens html/index.html in a browser
```

The HTML report shows each source file with surviving and killed mutants highlighted inline — green for killed (test caught it), red for survived (gap found).

**Artifacts** (both gitignored, local-only):
- `.mutmut-cache` — mutmut's SQLite run database; incremental re-runs skip already-tested mutations
- `html/` — generated HTML report

---

## Deployment

GitHub Actions workflow (`.github/workflows/job_alerts.yml`) runs at **6 AM, 12 PM, and 5 PM ET** daily, plus on-demand via `workflow_dispatch`. Only one cron entry is active at a time — currently EDT (`0 10,16,21 * * *`). Next DST adjustment: Nov 1, 2026 (switch to `0 11,17,22 * * *` for EST).

After each run, `seen_jobs.json` is force-committed back to the repo (`git add -f`, bypassing `.gitignore`) so job history persists across runs. `jobs_debug.json` and `resume.tex` are also committed after each run so they're available for the automated rule-improvement workflow.

**`improve_rules.yml`** triggers after each successful `job_alerts.yml` run (and via `workflow_dispatch` for manual testing). It runs Claude Code non-interactively to:
1. Read `jobs_debug.json`, `resume.tex`, `candidate_profile.yaml`, and the filtering/scoring source files
2. Scan every non-duplicate job across all result categories (qualified, filtered, scored_out) for false positives, false negatives, and scoring noise
3. Make surgical changes to `keyword_title_filter.py`, `candidate_profile.yaml`, or `resume_profile_builder.py` if evidence clearly justifies them
4. Run the full test suite and mypy; revert and exit if either fails
5. Open a PR with concrete evidence from `jobs_debug.json` cited in the body

**Required repository secrets:**

| Secret | Purpose |
|---|---|
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | Adzuna API credentials |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` | Outbound email (Gmail recommended) |
| `EMAIL_TO` | Recipient address |

**Optional secrets:**

| Secret | Purpose |
|---|---|
| `GEMINI_API_KEY` | Enables LLM title filtering via Gemini 2.0 Flash Lite (free tier) |
| `JSEARCH_API_KEY` | Enables JSearch/RapidAPI fetcher (2 additional sources) |
| `FEEDBACK_PAT` | Enables vote links in email cards; fine-grained PAT with `Contents: read/write` on this repo |
| `CLAUDE_CODE_OAUTH_TOKEN` | Required by `improve_rules.yml`; Claude Max subscription OAuth token — run `claude setup-token` locally to generate |

---

## Architecture

```
domain/          Core logic — Job, CandidateProfile, FilteringPolicy,
                 ScoringPolicy, ExperienceRequirement, domain events.
                 No external dependencies.

application/     JobProcessingService (orchestration), ResumeProfileBuilder,
                 JobRepository protocol, EventPublisher ABC.

infrastructure/  All I/O: job fetchers, LatexResumeParser, JsonJobRepository,
                 EmailNotifier, GeminiTitleFilter, KeywordTitleFilter,
                 in-memory event publisher.

tests/           pytest unit suite — one file per fetcher + job processing service.
                 All HTTP mocked; fixtures in tests/fixtures/.
tests/e2e/       E2E fetcher health checks — real HTTP calls, one test per fetcher.
                 Requires .env with Adzuna keys; skipped gracefully when absent.

pytest.ini       Registers the `e2e` pytest marker.

main.py          Wiring only — constructs all objects, runs fetcher pool,
                 writes jobs_debug.json, triggers email.
```

---

## Full Email Preview

To regenerate the screenshots after a run:

```bash
py screenshot_email.py                        # uses latest email in docs/emails/
py screenshot_email.py docs/emails/foo.html  # specific file
```

Outputs `docs/email_preview.png` (full page) and `docs/email_preview_cropped.png` (top crop used above).

![Full email preview](docs/email_preview.png)
