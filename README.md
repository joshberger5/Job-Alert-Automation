# Job Alert Automation

Scrapes job postings from 27 sources 3× daily, scores them against a candidate profile parsed from a resume PDF, and emails a formatted digest of qualified matches.

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
```

Place `resume.pdf` in the project root, then:

```bash
py main.py
```

---

## How It Works

### 1 — Profile Extraction

`PdfResumeParser` (pdfminer) extracts raw text from `resume.pdf`. `ResumeProfileBuilder` then constructs a `CandidateProfile` by:

- Locating the **Technical Skills** section and splitting it into categories. The first category (e.g. Languages) becomes `core_skills` with weight **4**; all remaining categories become `secondary_skills` with weight **2**.
- Scanning the **Experience** section for job titles by finding lines that immediately precede date lines.
- Hardcoding all other profile fields (`preferred_locations`, `remote_allowed`, `salary_minimum`, `ideal_max_experience_years`, `open_to_contract`) directly in `ResumeProfileBuilder.build()`.

### 2 — Fetching

All fetchers implement the `JobFetcher` protocol (`fetch() -> list[Job]`) and run **concurrently** via `ThreadPoolExecutor`. Each has a 120-second wall-clock timeout; a hung fetcher is skipped without blocking the rest.

| Source | Class | API Mechanism |
|---|---|---|
| Adzuna (local) | `AdzunaFetcher` | REST JSON — paginated, filters by keyword + location |
| Adzuna (remote, national) | `AdzunaFetcher` | Same API, `keywords="java developer remote"`, no location constraint, 3-day window |
| RemoteOK | `RemoteOKFetcher` | `remoteok.com/api?tags=java` — single JSON array, all results remote |
| We Work Remotely | `WeWorkRemotelyFetcher` | RSS XML feed — programming category; skips explicitly non-USA regions |
| SoFi, Robinhood, Brex, Plaid, Coinbase, DoorDash, Gusto, Checkr | `GreenhouseFetcher` | `boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true` — single request, all jobs |
| Dun & Bradstreet, Netlify, Greenhouse, Clipboard Health | `LeverFetcher` | `api.lever.co/v0/postings/{company}?mode=json` |
| Citi, Mayo Clinic (×2), PwC | `PhenomFetcher` | `/search-jobs/results` — paginated HTML fragment, regex-parsed for job hrefs; Mayo Clinic has a second instance with lat/lon for Tampa proximity |
| FIS Global | `WorkdayFetcher` | POST `/wday/cxs/fis/SearchJobs/jobs` — paginated JSON |
| SSC Technologies | `WorkdayFetcher` | POST `/wday/cxs/ssctech/SSCTechnologies/jobs` — descriptions fetched from job pages via ld+json, **parallelized** |
| VyStar Credit Union | `WorkdayFetcher` | Same as above |
| Bank of America (×2) | `BankOfAmericaFetcher` | `/services/jobssearchservlet` — one instance location-only, one with `keywords=Java`; deduplication handles overlap |
| Paysafe | `IcimsFetcher` | HTML scrape of `/tile-search-results/` (paginated, capped at 300 jobs); detail page per job, **parallelized** |
| FNF | `IcimsSitemapFetcher` | Parses `sitemap.xml` for job URLs, fetches `?in_iframe=1` on each to read ld+json, **parallelized** |

Detail-page fetches inside `WorkdayFetcher`, `IcimsFetcher`, and `IcimsSitemapFetcher` use `ThreadPoolExecutor(max_workers=10)` with an 8-second per-request timeout.

### 3 — Filtering

`FilteringPolicy.allows()` evaluates each job in order; first failing check eliminates the job:

1. **Contract filter** — rejected if `employment_type == "contract"` and `open_to_contract` is False.
2. **Experience gap filter** — `ExperienceRequirement.from_job_content()` tokenizes `"{title} {description}"` and finds the first number followed by a year token (`year`, `years`, `yrs`) within an 8-token window of the word `experience`. Handles `"15+"`, `"5-10 years"`, `"years,"`, `"years'"` etc. via leading-digit regex and punctuation stripping. Classified against `ideal_max_experience_years`:
   - `≤ max` → `WITHIN_IDEAL_RANGE` (pass)
   - `≤ max + 2` → `MODERATE_GAP` (reject)
   - `> max + 2` → `LARGE_GAP` (reject)
   - Not found → `UNKNOWN` (pass — benefit of the doubt)
3. **Remote check** — passes if:
   - `job.remote is True` **and** the location is US-accessible (strips "remote", checks remaining words against `{"us", "usa", "united", "states", "america", "worldwide", "global", "anywhere"}`; empty location passes), **or**
   - `job.remote is None` **and** the description/location contains an explicit remote phrase (`"fully remote"`, `"100% remote"`, `"work from home"`, etc.) **and** the location is US-accessible (prevents foreign on-site jobs from slipping through via description phrasing).
4. **Location check** — passes if any `preferred_locations` substring appears in `job.location` (case-insensitive).

### 4 — Scoring

`ScoringPolicy.evaluate()` operates on `"{title} {description}".lower()`:

- **+weight** for each skill found in content (`core_skills` weight 4, `secondary_skills` weight 2).
- **−2** for each skill in `job.required_skills` not present in the candidate's combined skill set (only applies when the fetcher populates `required_skills`; most don't — `RemoteOKFetcher` does via job tags).
- **Qualifies** if `score ≥ 7` (`ScoringPolicy.MINIMUM_SCORE`).

### 5 — Persistence

`JsonJobRepository` loads `seen_jobs.json` on startup and writes it after every `save()` call. Records are never expired — delete the file to reset. Schema:

```json
{
  "job_id": { "first_seen": "2026-03-01T09:00:00", "score": 12, "qualified": true }
}
```

Duplicate detection happens before filtering and scoring, so already-seen jobs cost only a dict lookup.

### 6 — Events & Output

`JobProcessingService` emits `JobEvaluated` and `JobQualified` domain events via `InMemoryEventPublisher` → `SimpleEventDispatcher`. Each job's result is recorded in `jobs_debug.json` with full score breakdown, filter reason, and metadata — `result` is one of `"duplicate"`, `"filtered_out"`, `"scored_out"`, `"qualified"`. Qualified jobs are printed to stdout and passed to `EmailNotifier`.

### 7 — Email

`EmailNotifier.send()` builds an HTML email (table-based, inline styles for client compatibility) containing:

- **Header**: qualified job count + run date.
- **Stats bar**: total jobs scanned, qualified count, wall-clock runtime.
- **Job cards**: one per qualified job — company, title, location, employment type, salary (if known), score badge (green ≥ 14, blue ≥ 10, amber ≥ 7), "View Job →" link.

Sent via SMTP STARTTLS. Skipped entirely if `SMTP_HOST` is not set.

---

## Deployment

GitHub Actions workflow (`.github/workflows/job_alerts.yml`) runs at **6 AM, 12 PM, and 5 PM ET** daily, plus on-demand via `workflow_dispatch`. (Cron times are UTC and require manual adjustment for DST — see comments in the workflow file.)

After each run, `seen_jobs.json` is force-committed back to the repo (`git add -f`, bypassing `.gitignore`) so job history persists across runs.

**Required repository secrets:**

| Secret | Purpose |
|---|---|
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | Adzuna API credentials |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` | Outbound email (Gmail recommended) |
| `EMAIL_TO` | Recipient address |

---

## Architecture

```
domain/          Core logic — Job, CandidateProfile, FilteringPolicy,
                 ScoringPolicy, ExperienceRequirement, domain events.
                 No external dependencies.

application/     JobProcessingService (orchestration), ResumeProfileBuilder,
                 JobRepository protocol, EventPublisher ABC.

infrastructure/  All I/O: job fetchers, PdfResumeParser, JsonJobRepository,
                 EmailNotifier, in-memory event publisher.

main.py          Wiring only — constructs all objects, runs fetcher pool,
                 writes debug output, triggers email.
```
