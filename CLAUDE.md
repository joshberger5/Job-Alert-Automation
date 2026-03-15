# CLAUDE.md

This file defines all behavioral rules for Claude Code when working on this project.
Read this file in full before starting any task.

---

## Environment

- **OS**: Windows 11, Claude Code shell is **bash** — use Unix-style syntax (`/dev/null`, forward slashes, etc.)
- **Python**: Use `py` (Windows alias) in all commands — `python` and `python3` are not aliased locally. Use `python` only when editing GitHub Actions YAML (Linux runner).
- Requires `resume.tex` in the project root and a `.env` file with `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`. Email is sent only when `SMTP_HOST` is also set.
- Output is written to `jobs_debug.json` each run.

---

## Commands

```bash
# Run the application
py main.py

# Run all unit tests (no network calls)
py -m pytest tests/ -v --ignore=tests/e2e/

# Run a single test file
py -m pytest tests/test_scoring_policy.py -v

# Run E2E fetcher health checks (real HTTP — requires .env with Adzuna keys)
py -m pytest tests/e2e/ -v

# Type-check (strict mode via mypy.ini)
py -m mypy .

# Mutation testing (local only — slow, do not add to CI)
py -m mutmut run           # run all mutations (domain/ + application/)
py -m mutmut results       # print summary to terminal
py -m mutmut html          # generate HTML report → html/index.html
```

**Run tests and mypy after every change** — do not commit broken tests or type errors.

E2E tests (`tests/e2e/`) are excluded from the standard test run and from mypy scope. Do not add type-checking for them in the workflow — they are checked only via the `E2E fetcher health check` CI step.

---

## Code Style

Always use explicit type annotations on every function parameter, return type, and local variable. No implicit `Any`, no bare `dict`/`list` without type args, no unannotated variables.

---

## File Deletion

**Never permanently delete files.** Move them to the `/trash` folder in the project root instead:

```bash
mkdir -p trash
mv path/to/file.py trash/file.py
```

- `/trash` is listed in `.gitignore` and will never be committed.
- Use timestamped filenames in trash if there is a naming conflict: `trash/file_20260309_143022.py`.

---

## Branching Strategy

All work is done on feature branches — **never commit directly to `main`**.

Branches follow the GSD naming convention: `gsd/phase-XX-name` (e.g. `gsd/phase-03-feedback`).

Do not merge branches to `main` — the developer handles all merges after review.

---

## Commit Frequency

**Commit extremely frequently.** After every meaningful unit of work:

- After implementing a single function
- After writing tests for that function
- After fixing a bug
- After updating a config value or type annotation
- After updating documentation or comments

Use conventional commit prefixes: `feat:`, `fix:`, `test:`, `refactor:`, `docs:`, `chore:`

Do not batch multiple unrelated changes into one commit.

---

## README and CLAUDE.md Updates

After **every change**, update `README.md` and `CLAUDE.md` in the same commit if their content needs to reflect the change. Do not defer these updates.

- `README.md` — update whenever behavior, configuration, secrets, fetchers, file outputs, or workflow change
- `CLAUDE.md` — update whenever a rule is wrong, outdated, or missing; this is a living document

---

## Context Management

Monitor context usage continuously. When context exceeds **55%**:

1. Create `_context_checkpoint.md` in the project root with: branch, what was completed, what remains, any blockers, and context % at time of writing.
2. Clear the context window.
3. Resume by reading `_context_checkpoint.md` first.

`_context_checkpoint.md` is in `.gitignore` and will never be committed.

---

## Web Search

Web search is permitted and encouraged when looking up API documentation, Python library usage, GitHub Actions syntax, or PowerShell command syntax. Only visit official documentation domains. Do not submit any data to external sites beyond read-only API calls in the job fetching pipeline.

---

## Architecture

Domain-Driven Design with three layers:

```
domain/           → Core business logic; zero external dependencies
application/      → Orchestration, use-case services, protocols
infrastructure/   → All I/O: fetchers, parsers, repository, email
docs/             → GitHub Pages feedback UI (feedback.html)
main.py           → Wiring only — no logic lives here
```

**See `DESIGN.md` for the full target design and all implementation decisions.**

### Data Flow (current state)

1. `LatexResumeParser` extracts plain text from `resume.tex` by stripping LaTeX markup
2. `ResumeProfileBuilder.build()` parses the "Technical Skills" section → **first category → `core_skills` (weight 4), all others → `secondary_skills` (weight 2)**. Experience/Projects sections are scanned for tertiary skills: tokens must appear ≥ 2 times, pass the taxonomy gate (`infrastructure/tech_taxonomy.yaml`), and optionally survive Gemini classification (cached in `infrastructure/tertiary_cache.json`). All preferences loaded from `candidate_profile.yaml`: `preferred_locations`, `remote_allowed`, `open_to_contract`, `minimum_salary`, `feedback_thumbs_down_reasons`, `feedback_thumbs_up_reasons`.
3. All fetchers run in parallel via `ThreadPoolExecutor`; each returns `list[Job]`. Fetcher wiring (instantiation and registry) is in `infrastructure/fetcher_registry.py`. Each fetcher is retried once on failure; persistent failures are collected as `FetcherFailure` TypedDicts (defined in `application/fetcher_result.py`).
4. `JobProcessingService.process()` iterates jobs, writing a debug record per job with `result` ∈ `{"duplicate", "filtered_out", "scored_out", "qualified"}`. After `ScoringPolicy.evaluate()`, `FeedbackBiasService.apply()` adjusts the score using vote history from `feedback.json`; `feedback_multiplier` is written to every scored record.
5. If `GEMINI_API_KEY` is set, `GeminiTitleFilter` runs one batch API call on all post-filter records. Qualified jobs the LLM rejects are re-marked `"llm_filtered"`. Scored-out jobs the LLM approves get `llm_relevant=True`.
6. `EmailNotifier.send()` sends one HTML email per run.

### Key Domain Classes

**`FilteringPolicy`** (`domain/filtering_policy.py`) passes a job if: not a contract (when `open_to_contract=False`), salary_max ≥ minimum_salary when both are known (fail-open when salary absent), experience gap is not MODERATE or LARGE, AND one of:
- `job.remote is True` and `_is_globally_or_us_remote(location)` returns True, OR
- `job.remote is None` and description mentions a remote phrase **and** location is US-accessible, OR
- location substring-matches a preferred location.

Check order: contract → salary floor → experience gap → remote/location.

`_is_globally_or_us_remote` strips "remote" then checks for `_US_WORDS = {"us", "usa", "united", "states", "america", "worldwide", "global", "anywhere"}`. Purely `"Remote"` (nothing else) also passes.

**`ExperienceRequirement`** (`domain/experience_requirement.py`) scans job content for patterns like `"5 years experience"`. `alignment_with(ideal_max)`: WITHIN_IDEAL_RANGE if `required ≤ ideal_max`, MODERATE_GAP if `required ≤ ideal_max + 4`, LARGE_GAP otherwise. MODERATE and LARGE gaps are filtered out.

**`FeedbackBiasService`** (`application/feedback_bias_service.py`) loads `feedback.json` on startup and builds a `bias_map: dict[str, int]` of reason-token → net votes. `apply(base_score, job_content, base_breakdown)` → `tuple[int, dict[str, int], float]`: tokens with `|net_votes| < 3` are skipped; others contribute `net_votes × FEEDBACK_WEIGHT (0.5)` to a multiplier clamped to `[0.5, 2.0]`. Returns `(final_score, updated_breakdown, clamped_multiplier)`. Fails open when `feedback.json` is absent.

**`ScoringPolicy`** (`domain/scoring_policy.py`): `+weight` per matched skill in job content, `−2` per required skill (from `job.required_skills`) that the candidate lacks. `MINIMUM_SCORE = 7` — increase to tighten, decrease to loosen. Only fetchers that populate `required_skills` (currently only `RemoteOKFetcher` via tags) incur missing-skill penalties.

**`GeminiTitleFilter`** (`infrastructure/llm_title_filter.py`) — optional relevance check using `gemini-2.0-flash-lite` (free tier). Fails open — any API error returns all IDs approved so no jobs are silently dropped.

**`JsonJobRepository`** (`infrastructure/json_job_repository.py`) persists `seen_jobs.json` — never expires. Delete to reset job history. Force-added by GitHub Actions despite `.gitignore`.

**`JobFetcher`** (`infrastructure/job_fetchers/__init__.py`) is a `Protocol` requiring only `fetch() -> list[Job]`. All fetchers must also expose `company_name: str`.

**`CandidateProfile`** (`domain/candidate_profile.py`) frozen dataclass fields: `preferred_locations`, `remote_allowed`, `ideal_max_experience_years`, `core_skills`, `secondary_skills`, `tertiary_skills`, `open_to_contract`, `minimum_salary` (default 0 = no filter), `feedback_thumbs_down_reasons` (default []), `feedback_thumbs_up_reasons` (default []).

### Adding a New Fetcher

1. Create `infrastructure/job_fetchers/your_fetcher.py` implementing `fetch() -> list[Job]` and exposing `company_name: str`
2. Set `job.remote = True` when definitively remote; `None` when unknown; `False` only if explicitly on-site
3. Populate `job.required_skills` only when the source provides structured skill tags
4. Import and instantiate in `infrastructure/fetcher_registry.py`'s `build_fetchers()` function

### Fetchers (current)

| Class | API style | Detail pages? |
|---|---|---|
| `AdzunaFetcher` | REST JSON (api.adzuna.com) | No |
| `AdzunaSimilarFetcher` | Scrapes "Similar jobs" section from Adzuna detail pages | Yes — parallel |
| `GreenhouseFetcher` | REST JSON (boards-api.greenhouse.io) | No |
| `LeverFetcher` | REST JSON (api.lever.co) | No |
| `WorkdayFetcher` | POST `/wday/cxs/…/jobs` | Optional (`fetch_descriptions=True`) — parallel |
| `BankOfAmericaFetcher` | `/services/jobssearchservlet` JSON | No |
| `IcimsFetcher` | HTML scrape (tile-search-results) | Yes — parallel |
| `IcimsSitemapFetcher` | sitemap.xml + JSON-LD per page | Yes — parallel |
| `RemoteOKFetcher` | REST JSON (remoteok.com/api) | No |
| `WeWorkRemotelyFetcher` | RSS XML feed | No |
| `LandstarFetcher` | Ceridian Dayforce POST JSON, paginated | No |
| `OracleFetcher` | Oracle Cloud HCM ICE REST (`/hcmRestApi/…/recruitingICEJobRequisitions`) | Yes — parallel |
| `JSearchFetcher` | RapidAPI JSearch (optional — requires `JSEARCH_API_KEY`) | No |

Detail-page fetches are parallelized with `ThreadPoolExecutor(max_workers=10)`, **12s per request**, **120s batch cap** (`_DETAIL_TIMEOUT = 12`, `_DETAIL_BATCH_TIMEOUT = 120`).

`PhenomFetcher` exists but is not wired in — Phenom endpoints now return empty results (client-side rendering).

**Oracle ICE auth caveat** — the ICE endpoint is unauthenticated for *most* public career sites, but `jpmc.fa.oraclecloud.com` returns **401** in live runs. CSX and Florida Blue have returned SSL errors so their auth status is unconfirmed. If Oracle fetchers consistently 401, they may need to be removed or replaced with a scraping approach.

---

## Salary Parsing

All salary string parsing goes through the shared `SalaryParser` helper in `infrastructure/salary_parser.py`. Do not inline salary parsing in fetchers.

Supported formats:
- `$90,000 – $120,000` → 120000
- `$60k – $90k` → 90000
- `$60-90k` → 90000
- `$60,000 to $90,000` → 90000
- `$60 to $90k` → 90000
- `$85,000` (single value) → 85000
- `None` or unparseable → `None`

---

## Fanatics Deduplication Note

Fanatics posts on both Lever (`jobs.lever.co/fanatics`) and Greenhouse (`job-boards.greenhouse.io/fanaticsinc`). The same job may appear from both fetchers with different IDs. Standard `seen_jobs.json` dedup operates on job ID only and will not catch this. Consider a secondary dedup key based on `normalize(title + company)` hash.

---

## GitHub Actions

`.github/workflows/job_alerts.yml` — runs at 6 AM, 12 PM, 5 PM ET daily. Also supports `workflow_dispatch`. Commits `seen_jobs.json` back after each run (`git add -f` force-adds despite `.gitignore`).

Workflow steps (in order):
1. **Type check** — `mypy domain/ application/ infrastructure/ main.py`
2. **Run tests** — `pytest tests/ -v --ignore=tests/e2e/` (unit tests only)
3. **E2E fetcher health check** — `pytest tests/e2e/ -v` with `continue-on-error: true`; reports per-fetcher pass/fail without blocking the workflow
4. **Run job alerts** — `python main.py`
5. **Persist seen jobs** — force-commits `seen_jobs.json`

**DST Reminder** — cron does not auto-adjust for DST. Only **one** cron entry should be active at a time.

- **Current (EDT, active Mar–Nov 2026)**: `0 10,16,21 * * *`
- **Next adjustment Nov 1, 2026 (EST starts)**: change to `0 11,17,22 * * *`

Always update the comment in the workflow file to reflect the next adjustment date when you touch it.

Required secrets: `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `EMAIL_TO`, `FEEDBACK_PAT`
Optional: `GEMINI_API_KEY`, `JSEARCH_API_KEY`

---

## .gitignore Entries Required

```
/trash/
_context_checkpoint.md
jobs_debug.json
infrastructure/tertiary_cache.json
.mutmut-cache
html/
```

Note: `jobs_debug.json` is committed by GitHub Actions using `git add -f`, bypassing `.gitignore`. It should still be listed to prevent accidental local commits. `tertiary_cache.json` is a local Gemini classification cache — never commit it. `.mutmut-cache` is mutmut's run database; `html/` is the generated report — both are local-only.
