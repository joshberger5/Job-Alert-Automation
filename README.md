# Job Alert Automation

Scrapes job postings from 23 sources 3× daily, scores them against a candidate profile parsed from a LaTeX resume, optionally filters titles with a Gemini LLM pass, and emails a formatted digest of qualified matches.

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
- Scanning the **Experience** and **Projects** sections for capitalized tokens, then applying two filters: (1) **frequency gate** — tokens appearing only once are dropped; (2) **taxonomy gate** — tokens are checked against `infrastructure/tech_taxonomy.yaml` (61 curated tech terms). Taxonomy hits are always included. Unknown tokens are optionally classified by Gemini (when `GEMINI_API_KEY` is set) and cached in `infrastructure/tertiary_cache.json`; without a key, unknown tokens are kept (fail-open). Survivors become `tertiary_skills` with weight **1**.
- Calculating `ideal_max_experience_years` by summing date-range durations found in the **Experience** section (total months ÷ 12, rounded down).
- Loading all preferences from `candidate_profile.yaml`: `preferred_locations`, `remote_allowed`, `open_to_contract`, `minimum_salary`, `feedback_thumbs_down_reasons`, `feedback_thumbs_up_reasons`.

### 2 — Fetching

All fetchers implement the `JobFetcher` protocol (`fetch() -> list[Job]`) and run **concurrently** via `ThreadPoolExecutor`. Each has a 120-second wall-clock timeout; a hung fetcher is skipped without blocking the rest.

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
| Landstar System | `LandstarFetcher` | POST `jobs.dayforcehcm.com/api/geo/landstar/jobposting/search` (Ceridian Dayforce) — paginated JSON; salary extracted from description text |
| Bank of America (×2) | `BankOfAmericaFetcher` | `/services/jobssearchservlet` — one instance location-only, one with `keywords=Java`; deduplication handles overlap |
| Paysafe | `IcimsFetcher` | HTML scrape of `/tile-search-results/` (paginated, capped at 300 jobs); detail page per job, **parallelized** |
| FNF | `IcimsSitemapFetcher` | Parses `sitemap.xml` for job URLs, fetches `?in_iframe=1` on each to read ld+json, **parallelized** |

Detail-page fetches inside `WorkdayFetcher`, `IcimsFetcher`, and `IcimsSitemapFetcher` use `ThreadPoolExecutor(max_workers=10)` with an 8-second per-request timeout.

### 3 — Filtering

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

### 4 — Scoring

`ScoringPolicy.evaluate()` operates on `"{title} {description}".lower()`:

- **+weight** for each skill found in content (`core_skills` weight 4, `secondary_skills` weight 2, `tertiary_skills` weight 1).
- **−2** for each skill in `job.required_skills` not present in the candidate's combined skill set (only applies when the fetcher populates `required_skills`; most don't — `RemoteOKFetcher` does via job tags).
- **Qualifies** if `score ≥ 7` (`ScoringPolicy.MINIMUM_SCORE`).

After scoring, `FeedbackBiasService` applies a personal multiplier derived from feedback vote history (`feedback.json`). Reason tokens with ≥ 3 net votes contribute `net_votes × 0.5` to the multiplier, clamped to `[0.5, 2.0]`. The adjusted score determines `"qualified"` or `"scored_out"`, and `feedback_multiplier` is written to `jobs_debug.json`.

### 5 — LLM Title Filtering (optional)

When `GEMINI_API_KEY` is set, `GeminiTitleFilter` runs a single batch call to `gemini-2.0-flash-lite` (free tier) on all post-filter records (`"qualified"` + `"scored_out"`). The prompt is built from `profile.core_skills` and `profile.ideal_max_experience_years` and asks the model to identify which job titles are genuine software engineering roles for the candidate.

- **Qualified jobs the LLM rejects** are re-marked `"llm_filtered"` and excluded from the email's main section (but still shown in a secondary section).
- **Scored-out jobs the LLM approves** get `llm_relevant=True` added to their debug record and appear in a third email section.
- **Fails open** — any API error returns all IDs, so no jobs are silently dropped.

### 6 — Persistence

`JsonJobRepository` loads `seen_jobs.json` on startup and writes it after every `save()` call. Records are never expired — delete the file to reset. Schema:

```json
{
  "job_id": { "first_seen": "2026-03-01T09:00:00", "score": 12, "qualified": true }
}
```

Duplicate detection happens before filtering and scoring, so already-seen jobs cost only a dict lookup.

### 7 — Events & Debug Output

`JobProcessingService` emits `JobEvaluated` and `JobQualified` domain events via `InMemoryEventPublisher` → `SimpleEventDispatcher`. Each job's result is recorded in `jobs_debug.json` with full score breakdown, filter reason, and metadata. The `result` field is one of:

| Value | Meaning |
|---|---|
| `"duplicate"` | Already seen in a previous run — skipped immediately |
| `"filtered_out"` | Failed `FilteringPolicy` (contract, experience gap, or location) |
| `"scored_out"` | Passed filtering but `score < MINIMUM_SCORE` |
| `"qualified"` | Passed filtering and scoring |
| `"llm_filtered"` | Passed scoring but LLM flagged the title as irrelevant |

### 8 — Email

`EmailNotifier.send()` builds an HTML email (table-based, inline styles for client compatibility) with up to three sections:

- **Qualified jobs** — always present when any exist. One card per job: company, title, location, employment type, salary (if known), score badge (green ≥ 14, blue ≥ 10, amber ≥ 7), "View Job →" link. Each section is collapsible.
- **LLM Rejected** — jobs that scored high enough but were flagged by the LLM title filter. Shown only when `GEMINI_API_KEY` is set and at least one job was re-classified.
- **Possibly Relevant** — scored-out jobs that the LLM considers worth a look. Shown only when `GEMINI_API_KEY` is set and any such jobs exist.

Sent via SMTP STARTTLS. Skipped entirely if `SMTP_HOST` is not set.

---

## Tests

```bash
py -m pytest tests/ -v
```

131 tests across 16 files, all passing with no network calls (all HTTP is mocked via `unittest.mock.patch`).

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
| `test_keyword_title_filter.py` | 6 | Rejection fragments (`data scientist`, `product manager`), case-insensitivity, approved engineering titles, custom fragment override |
| `test_filtering_policy.py` | 15 | Contract filter, salary floor (below/above/missing/disabled), experience gap filter, remote=True/None/Europe logic, preferred-location substring match |
| `test_landstar_fetcher.py` | 19 | Field mapping, salary (annual + hourly→annual conversion, absent), remote detection (`hasVirtualLocation`, title, description), multi-location formatting, pagination, error handling |
| `test_adzuna_similar_fetcher.py` | 10 | Job extraction from "Similar jobs" section, ID/salary/URL parsing, cross-seed deduplication, graceful degradation on HTTP errors and missing section |
| `test_resume_profile_builder.py` | 6 | `minimum_salary` and reason tags loaded from YAML; taxonomy-gated tertiary extraction (single-occurrence excluded, taxonomy hit included, fail-open when no Gemini key) |
| `test_feedback_bias_service.py` | 9 | No-file → multiplier 1.0; below-threshold token skipped; at-threshold token applied; min/max clamp (0.5/2.0); score delta in breakdown |

Fixtures (JSON, HTML, RSS) live in `tests/fixtures/` — either trimmed real API responses or synthetic data matching the exact schema each fetcher expects.

---

## Deployment

GitHub Actions workflow (`.github/workflows/job_alerts.yml`) runs at **6 AM, 12 PM, and 5 PM ET** daily, plus on-demand via `workflow_dispatch`. Only one cron entry is active at a time — currently EDT (`0 10,16,21 * * *`). Next DST adjustment: Nov 1, 2026 (switch to `0 11,17,22 * * *` for EST).

After each run, `seen_jobs.json` is force-committed back to the repo (`git add -f`, bypassing `.gitignore`) so job history persists across runs.

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

---

## Architecture

```
domain/          Core logic — Job, CandidateProfile, FilteringPolicy,
                 ScoringPolicy, ExperienceRequirement, domain events.
                 No external dependencies.

application/     JobProcessingService (orchestration), ResumeProfileBuilder,
                 JobRepository protocol, EventPublisher ABC.

infrastructure/  All I/O: job fetchers, LatexResumeParser, JsonJobRepository,
                 EmailNotifier, GeminiTitleFilter, in-memory event publisher.

tests/           pytest suite — one file per fetcher + job processing service.
                 All HTTP mocked; fixtures in tests/fixtures/.

main.py          Wiring only — constructs all objects, runs fetcher pool,
                 writes jobs_debug.json, triggers email.
```
