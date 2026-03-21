# Job Alert Automation — Design Document

This document captures the full business logic and all concrete implementation decisions in the
system. It is the source of truth before implementation. Read it fully, ask questions if anything
is ambiguous, then implement against it.

---

## 0. Implementation Instructions for Claude Code

Before starting any implementation work, read `CLAUDE.md` in full. All behavioral rules for
branching, committing, testing, file deletion, context management, and web access are defined
there.

---

## 1. What the System Does (High Level)

Runs 3× per day (6 AM, 12 PM, 5 PM ET) via GitHub Actions. Each run:

1. Parses `resume.tex` to build a `CandidateProfile`.
2. Loads `feedback.json` to apply personal scoring adjustments.
3. Fetches jobs from all sources in parallel.
4. For each job: marks as duplicate (skip), filtered-out, scored-out, or qualified.
5. Runs a two-stage title filter (keyword blocklist → optional Gemini LLM) on qualified +
   scored-out jobs.
6. Sends an HTML email digest (always — even if no qualified jobs found).
7. Writes `jobs_debug.json` with every job's result and score breakdown, and commits it to the
   repo.
8. Commits `seen_jobs.json` back to the repo so history persists across runs.
9. Archives feedback votes older than 90 days from `feedback.json`.

---

## 2. Candidate Profile

### 2.1 Where preferences come from

Two sources are combined at startup:

| Preference | Source |
|---|---|
| `preferred_locations` | `candidate_profile.yaml` in project root |
| `remote_allowed` | `candidate_profile.yaml` |
| `open_to_contract` | `candidate_profile.yaml` |
| `minimum_salary` | `candidate_profile.yaml` |
| `feedback_thumbs_down_reasons` | `candidate_profile.yaml` (configurable tag list) |
| `feedback_thumbs_up_reasons` | `candidate_profile.yaml` (configurable tag list) |
| `core_skills` | Parsed from `resume.tex` — Technical Skills section, **first category** |
| `secondary_skills` | Parsed from `resume.tex` — Technical Skills section, **all other categories** |
| `tertiary_skills` | Auto-extracted tokens from Experience + Projects sections of `resume.tex` |
| `ideal_max_experience_years` | Calculated by summing date-range durations in the Experience section of `resume.tex` |

**`candidate_profile.yaml` example:**
```yaml
preferred_locations:
  - Jacksonville
  - Orange Park
  - St. Augustine
  - Saint Augustine
  - St. Johns
  - Saint Johns
  - Fleming Island
  - Nocatee
  - Ponte Vedra
  - Fernandina Beach
remote_allowed: true
open_to_contract: false
minimum_salary: 85000

feedback_thumbs_down_reasons:
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
```

### 2.2 Skill extraction from resume

The LaTeX is stripped to plain text first. Then:

- The **Technical Skills** section is located by regex.
- Lines are parsed as `Category: skill1, skill2, skill3`.
- **First category line** (e.g. "Languages: Java, Python, ...") → `core_skills` with weight **4**.
- **All remaining category lines** (e.g. "Frameworks: Spring Boot, ...") → `secondary_skills`
  with weight **2**.
- The **Experience** and **Projects** sections are scanned for additional tokens →
  `tertiary_skills` with weight **1**.

**Tertiary skill extraction — improvement needed:**
The current token-based heuristic is noisy and should be replaced with a smarter approach:
- Validate extracted tokens against a curated tech taxonomy of known technologies
- Filter out all-caps abbreviations that are not recognized tech terms
- Ignore tokens that appear only once across the entire resume
- Consider using the Gemini LLM to classify ambiguous tokens as "tech skill" vs "noise"
  (only if `GEMINI_API_KEY` is set; fall back to taxonomy-only otherwise)

Weights are fixed constants. There is no configuration to change them other than editing the
source code.

### 2.3 Experience calculation

The `ideal_max_experience_years` field is derived automatically from the resume:

- The Experience section is scanned for date ranges matching patterns like:
  `"Month Year – Month Year"`, `"Month Year – Present"`, `"Month – Month Year"` (same year).
- All durations are summed and converted to years (floor division by 12).
- **This is used as the upper bound for the experience gap filter**, not as years of experience
  to advertise — it represents how much experience the candidate actually has, so jobs requiring
  more than this are filtered.

---

## 3. Job Data Model

Each job has these fields (all from `domain/job.py`):

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Unique identifier — format varies by fetcher |
| `title` | `str` | Job title |
| `company` | `str` | Company name |
| `location` | `str` | Raw location string from source |
| `description` | `str` | Plain text (HTML stripped by fetcher) |
| `salary` | `str \| None` | Formatted string, e.g. `"$90,000 – $120,000"` |
| `salary_max` | `int \| None` | Parsed upper bound of salary range in dollars (used for filtering) |
| `url` | `str \| None` | Direct link to the job posting |
| `required_skills` | `list[str]` | Structured skill tags — only populated by RemoteOK |
| `remote` | `bool \| None` | `True` = confirmed remote; `None` = unknown; `False` = confirmed on-site |
| `employment_type` | `str \| None` | `"permanent"`, `"contract"`, `"part_time"`, `"internship"`, or `None` |

**Key design choice**: `remote=None` means "we don't know" and is treated differently from
`remote=False`. A job with `remote=None` can still pass the remote check if the description
explicitly says it's remote.

---

## 4. Pipeline Stage 1 — Fetching

All fetcher instances run concurrently via `ThreadPoolExecutor`. Each has a 120-second
wall-clock timeout — a hung fetcher is skipped without blocking the rest. Each fetcher gets
**one retry** on failure before being marked as failed. Failed fetchers are reported in the
email digest.

### 4.1 Fetcher inventory

| Label | Class | Mechanism |
|---|---|---|
| Adzuna (local) | `AdzunaFetcher` | REST JSON, paginated, keyword + location filter |
| Adzuna (remote/national) | `AdzunaFetcher` | Same API, `keywords="java remote"`, national, 3-day window |
| Adzuna (similar) | `AdzunaSimilarFetcher` | Gets seed URLs from API, scrapes "Similar jobs" section, then follows each job URL to fetch full description |
| JSearch (local) | `JSearchFetcher` | RapidAPI — `"java developer Jacksonville FL"`, 3-day window. Optional: skipped + warning if `JSEARCH_API_KEY` not set |
| JSearch (remote) | `JSearchFetcher` | RapidAPI — `"java developer remote"`, 3-day window. Same key requirement |
| RemoteOK | `RemoteOKFetcher` | `remoteok.com/api?tags=java` — also the only fetcher that populates `required_skills` |
| We Work Remotely | `WeWorkRemotelyFetcher` | RSS XML feed, programming category, skips non-USA regions |
| Netflix | `WorkdayFetcher` | `netflix.wd1.myworkdayjobs.com` |
| SoFi | `GreenhouseFetcher` | Greenhouse boards API |
| DoorDash | `GreenhouseFetcher` | Greenhouse boards API |
| Fanatics (Greenhouse) | `GreenhouseFetcher` | `job-boards.greenhouse.io/fanaticsinc` — may overlap with Fanatics Lever; dedup handles it |
| Fanatics (Lever) | `LeverFetcher` | `jobs.lever.co/fanatics` — may overlap with Fanatics Greenhouse; dedup handles it |
| Dun & Bradstreet | `LeverFetcher` | Lever API |
| Allstate | `WorkdayFetcher` | Workday POST, descriptions fetched from job pages (parallelized) |
| GEICO | `WorkdayFetcher` | Workday POST, descriptions fetched from job pages (parallelized) |
| FIS Global | `WorkdayFetcher` | Workday POST, no detail pages |
| SSC Technologies | `WorkdayFetcher` | Workday POST, descriptions fetched from job pages (parallelized) |
| VyStar Credit Union | `WorkdayFetcher` | Workday POST, descriptions fetched from job pages (parallelized), Jacksonville location filter |
| Citi | `WorkdayFetcher` | `citi.wd5.myworkdayjobs.com` |
| Landstar System | `LandstarFetcher` | Ceridian Dayforce POST JSON, paginated, salary extracted from description text |
| Bank of America (location) | `BankOfAmericaFetcher` | Internal JSON API, Jacksonville only |
| Bank of America (keyword) | `BankOfAmericaFetcher` | Same API, Jacksonville + keyword=Java |
| Paysafe | `IcimsFetcher` | HTML scrape, tile-search-results, detail page per job (parallelized) |
| FNF | `IcimsSitemapFetcher` | Parses sitemap.xml, fetches ld+json from each job page (parallelized) |
| JPMorgan Chase | `OracleFetcher` | `jpmc.fa.oraclecloud.com` — **requires new OracleFetcher class, more dev work** |
| CSX | TBD | Jacksonville HQ — **ATS needs verification before implementation** |
| Florida Blue | TBD | Jacksonville HQ — **ATS needs verification before implementation** |
| Availity | TBD | Jacksonville HQ — **ATS needs verification before implementation** |

### 4.2 How fetchers set `remote`

Each fetcher is responsible for inferring `remote`. The shared helper `infer_remote(location)` is
used by most:

- Returns `True` if location contains "remote" (case-insensitive).
- Returns `None` otherwise.
- Returns `False` only when a fetcher explicitly knows the role is on-site — currently no
  fetcher sets `False` in practice; `None` is the default unknown state.

### 4.3 Salary parsing

A shared helper `parse_salary_max(salary_string)` extracts the upper bound of a salary range
and returns it as an integer (dollars). It must handle all of these formats:

- `$90,000 – $120,000` → 120000
- `$60k – $90k` → 90000
- `$60-90k` → 90000
- `$60,000 to $90,000` → 90000
- `$60 to $90k` → 90000
- `$85,000` (single value) → 85000
- `None` or unparseable → `None`

The parsed value is stored in `job.salary_max` and used by the salary filter.

---

## 5. Pipeline Stage 2 — Duplicate Detection

Before any filtering or scoring, each job's `id` is checked against `seen_jobs.json`.

- If found → `result = "duplicate"`, job is skipped entirely.
- If not found → continues to filtering.

`seen_jobs.json` is **never expired**. The only way to reprocess old jobs is to delete the file.

**Stored record per job:**
```json
{
  "job_id": {
    "first_seen": "2026-03-01T09:00:00",
    "score": 12,
    "qualified": true
  }
}
```

---

## 6. Pipeline Stage 3 — Filtering

`FilteringPolicy.allows()` runs five checks in order. **First failure eliminates the job.**

### 6.1 Employment type filter

```
if open_to_contract is False AND job.employment_type == "contract":
    → filtered_out
if job.employment_type == "internship":
    → filtered_out
if job.employment_type == "part_time":
    → filtered_out
```

Only exact string matches trigger this. `"permanent"` and `None` pass.

### 6.2 Salary filter

```
if job.salary_max is not None AND job.salary_max < profile.minimum_salary:
    → filtered_out
```

Jobs with `salary_max = None` (salary not listed or unparseable) always pass.

### 6.3 Experience gap filter

Skipped entirely if `ideal_max_experience_years == 0`.

Otherwise, scans `"{title} {description}".lower()` for the first occurrence of a number
followed by a year-token (`year`, `years`, `yrs`) within an 8-token window of the word
`experience` (or `experiences`, `experienced`, `exp`).

**Gap classification:**
```
required ≤ ideal_max                  → WITHIN_IDEAL_RANGE  (pass)
required ≤ ideal_max + 4              → MODERATE_GAP         (filtered out)
required > ideal_max + 4              → LARGE_GAP            (filtered out)
not found                             → UNKNOWN              (pass — benefit of the doubt)
```

### 6.4 Remote check (only if `remote_allowed` is True)

**Case A** — job explicitly marked remote:
```
job.remote is True
AND location is US-accessible
```

US-accessible means: strip the word "remote" from the location string, then check if any
remaining word is in `{"us", "usa", "united", "states", "america", "worldwide", "global",
"anywhere"}`. A location of purely `"Remote"` (nothing else after stripping) also passes.

**Case B** — remote unknown, but description says so:
```
job.remote is None
AND description/location contains an explicit remote phrase
AND location is US-accessible
```

Explicit remote phrases (any one must match):
- `"fully remote"`, `"100% remote"`, `"work from home"`, `"wfh"`, `"remote position"`,
  `"remote role"`, `"remote only"`, `"remote-only"`, `"this is a remote"`,
  `"remote work environment"`

**Case C** — `job.remote is False`: never passes the remote check (must pass location check
instead).

### 6.5 Location check

```
any(preferred_location.lower() in job.location.lower()
    for preferred_location in profile.preferred_locations)
```

Substring match only. `preferred_locations` is defined in `candidate_profile.yaml` and
currently includes: Jacksonville, Orange Park, St. Augustine, Saint Augustine,
St. Johns, Saint Johns, Fleming Island, Nocatee, Ponte Vedra, Fernandina Beach.

If neither the remote check nor the location check passes → `result = "filtered_out"`.

---

## 7. Pipeline Stage 4 — Scoring

`ScoringPolicy.evaluate()` runs on `"{title} {description}".lower()`.

### 7.1 Skill hit scoring

For each skill in the candidate profile, if the skill appears as a **whole word** (regex word
boundary `\b`) in the job content:

- `core_skills` hit: **+4**
- `secondary_skills` hit: **+2**
- `tertiary_skills` hit: **+1**

Each skill is counted once regardless of how many times it appears.

### 7.2 Personal score adjustment (feedback-based)

After base skill scoring, a personal multiplier is applied based on `feedback.json`. If jobs
with a certain skill pattern or title keyword have consistently received 👎 votes, those patterns
are down-weighted. If 👍 jobs share traits, those are boosted. The base weights remain unchanged;
the adjustment is a separate additive or multiplicative layer.

The exact algorithm:
- For each 👎 job in feedback: identify skills/title tokens that appeared in that job
- For each 👍 job in feedback: same
- Build a personal bias map: `{token: net_vote_score}` where each 👍 = +1, each 👎 = −1
- Apply: for each token in the bias map that appears in the current job, add
  `bias_score * FEEDBACK_WEIGHT` to the total score
- `FEEDBACK_WEIGHT` = 0.5 (constant, source-editable only)
- Only tokens with |net_vote_score| ≥ 3 are included (minimum signal threshold)

### 7.3 Missing-skill penalty

Only applies when `job.required_skills` is non-empty. Currently **only RemoteOK** populates
this field (from job tags).

**Known limitation**: the penalty only fires for RemoteOK jobs. If it cannot be extended to
parse required skills from job descriptions for other fetchers, remove the penalty entirely to
avoid unfairly disadvantaging only RemoteOK jobs.

For each skill in `job.required_skills` that is NOT in the candidate's combined skill set
(core + secondary + tertiary): **−0.5**.

### 7.4 Qualification threshold

```
score >= MINIMUM_SCORE (currently 5)  → "qualified"
score <  MINIMUM_SCORE                → "scored_out"
```

The score breakdown (e.g. `{"core:java": 4, "secondary:spring": 2, "missing:rust": -0.5}`) is
written to `jobs_debug.json` for every job.

---

## 8. Pipeline Stage 5 — Title Filtering

Runs after scoring on all `"qualified"` and `"scored_out"` records. Two stages always run in
order.

### 8.1 Keyword filter (always runs)

Fast, local, no API calls. Rejects any job whose title contains one of these substrings
(case-insensitive):

- Data / ML: `data scientist`, `data engineer`, `machine learning`, `ml engineer`,
  `research scientist`, `research engineer`
- Product / Design: `product manager`, `product owner`, `program manager`, `ux designer`,
  `ui designer`, `product designer`, `graphic designer`, `visual designer`,
  `interaction designer`
- Finance / Legal: `financial analyst`, `quantitative analyst`, `quant analyst`,
  `accountant`, `economist`, `attorney`, `paralegal`, `compliance officer`
- People / Recruiting: `recruiter`, `talent acquisition`, `human resources`
- Sales / Marketing: `account executive`, `account manager`, `sales representative`,
  `sales associate`, `inside sales`, `marketing manager`, `marketing specialist`
- Operations: `operations manager`, `manual qa`, `manual tester`, `manual test`

Effect on records:
- `"qualified"` job whose title matches a fragment → re-marked `"llm_filtered"`
- `"scored_out"` job whose title matches → stays `"scored_out"` (not surfaced anywhere)

### 8.2 LLM filter (optional, requires `GEMINI_API_KEY`)

Runs only on jobs that passed the keyword filter. Uses `gemini-2.0-flash-lite` (free tier).
One batch API call per run with all candidate titles.

**Prompt tells the model:**
- Candidate's core skills (from profile)
- Experience level: `0–{ideal_max_experience_years} years`
- KEEP: backend, full-stack, Java developer, software engineer, platform engineer, DevOps,
  SRE, mobile, QA automation, etc.
- REJECT: data scientist, data engineer, ML engineer, economist, accountant, financial
  analyst, designer, product manager, sales, marketing, HR, legal, operations, recruiter,
  pure manual QA
- Return a JSON array of 0-based indices

Effect on records:
- `"qualified"` job the LLM rejects → `"llm_filtered"` (shown in email's LLM Rejected section)
- `"scored_out"` job the LLM approves → gets `llm_relevant=True` (shown in email's
  Possibly Relevant section)
- **Fails open**: any API error returns all IDs approved, so no jobs are silently dropped

---

## 9. Email

Sent via SMTP STARTTLS. **Always sent** — even when there are no qualified jobs.

HTML email (table-based, inline styles for client compatibility). Up to five sections:

### Section 1 — Qualified Jobs
Always present (even if empty — shows "No new qualified jobs this run" message). Jobs are
**sorted by score descending**. One card per job:
- Company, title, location, employment type
- Salary (if known)
- Score badge: green if ≥ 11, blue if ≥ 8, amber if ≥ 5
- "View Job →" link
- 👍 / 👎 feedback buttons (plain URL links — see Section 10)

### Section 2 — Possibly Relevant
Shows `"scored_out"` jobs that are likely relevant based on title, even without Gemini.
Uses a keyword **passlist** of relevant title fragments (e.g. `software engineer`, `developer`,
`backend`, `full stack`, `java`, `platform engineer`, `devops`, `sre`, `mobile engineer`,
`qa automation`). Any scored-out job whose title matches a passlist fragment is included here.
When `GEMINI_API_KEY` is set, `llm_relevant=True` jobs are also included.

### Section 3 — LLM Rejected
Only shown when `GEMINI_API_KEY` is set and at least one job was re-classified to
`"llm_filtered"`. Useful for catching false negatives in the LLM filter.

### Section 4 — Run Summary
Always present. Shows:
- Total jobs fetched, duplicates skipped, filtered out, scored out, qualified
- Which fetchers ran successfully
- Which fetchers failed (after retry) — shown prominently if any

### Section 5 — Weekly Pattern Summary
Shown once per week (on the first run of Monday). Only appears when `feedback.json` contains
≥ 20 votes. Analyzes patterns in thumbs-down votes and suggests blocklist additions. Example:
*"You've thumbs-downed 8 jobs with 'Senior' in the title — consider adding it to the keyword
blocklist."*

### Missing optional keys warning
If `JSEARCH_API_KEY` is not set, include a one-line note in the Run Summary section:
*"JSearch fetcher skipped — set JSEARCH_API_KEY in GitHub Actions secrets to enable."*

---

## 10. Feedback System

Allows the user to rate each qualified job as 👍 or 👎 with a preset reason tag. Votes are
stored in `feedback.json` and used to adjust scoring (see Section 7.2).

### 10.1 Flow

1. Each job card in the email contains two plain URL links: 👍 and 👎
2. Clicking a link opens a **GitHub Pages static page** (hosted in the same repo under
   `docs/feedback.html`) passing the job ID and vote direction as URL query parameters
3. The page displays the preset reason tags from `candidate_profile.yaml`
4. Selecting a reason tag fires a `repository_dispatch` event to GitHub Actions via the
   GitHub API (using a fine-grained PAT stored as `FEEDBACK_PAT` secret)
5. A dedicated GitHub Actions workflow (`feedback.yml`) receives the dispatch, appends the
   vote to `feedback.json`, and commits it

### 10.2 feedback.json structure

```json
[
  {
    "job_id": "abc123",
    "title": "Senior Java Developer",
    "company": "Acme Corp",
    "vote": "down",
    "reason": "Too senior",
    "voted_at": "2026-03-09T14:30:00"
  }
]
```

### 10.3 Archival

On each run, votes older than 90 days are moved to `feedback_archive_YYYY_MM.json` (one file
per month) and removed from `feedback.json`. Archive files are committed to the repo.

### 10.4 Required secrets

- `FEEDBACK_PAT` — fine-grained GitHub personal access token with `repo` scope, used by the
  GitHub Pages feedback UI to trigger the `repository_dispatch` event

---

## 11. Persistence

`seen_jobs.json` — persists job history across all runs.

- Loaded at startup. Written after every job is processed (`save()` call).
- `repository.flush()` at end of run writes the final state to disk.
- **Never expires** — delete the file to reset.
- Force-committed back to the repo by GitHub Actions after each run (`git add -f`),
  bypassing `.gitignore`.

`jobs_debug.json` — written every run **and committed to the repo**.

- Contains: `run_at`, `total_fetched`, summary counts, and full list of all job records with
  `result`, `score`, `breakdown`, and all metadata.
- Use this to diagnose why a specific job was filtered or scored out.

`feedback.json` — persists user votes across runs. Committed after every vote.

`feedback_archive_YYYY_MM.json` — monthly archive of votes older than 90 days.

---

## 12. GitHub Actions Deployment

File: `.github/workflows/job_alerts.yml`

### Schedule

Target times: **6 AM, 12 PM, 5 PM ET**.

- During EDT (mid-March – early November, UTC−4): `0 10,16,21 * * *`
- During EST (early November – mid-March, UTC−5): `0 11,17,22 * * *`

**Note**: GitHub Actions cron does not auto-adjust for DST. The schedule must be manually
updated twice per year. Add a comment in the workflow file noting the next adjustment date.

### Triggers
- Scheduled cron (above)
- Manual `workflow_dispatch`

### Required secrets
- `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`
- `EMAIL_TO`
- `FEEDBACK_PAT`

### Optional secrets
- `GEMINI_API_KEY` — enables LLM title filtering
- `JSEARCH_API_KEY` — enables JSearch fetcher (warn in email if missing)

---

## 13. Architecture

```
domain/          Job, CandidateProfile, FilteringPolicy, ScoringPolicy,
                 ExperienceRequirement — pure logic, zero external deps.

application/     JobProcessingService (orchestrates one job at a time),
                 ResumeProfileBuilder, TitleFilterService, FeedbackService,
                 JobRecord TypedDict, protocol definitions (JobRepository,
                 EventPublisher).

infrastructure/  All I/O: job fetchers, LatexResumeParser, JsonJobRepository,
                 EmailNotifier, GeminiTitleFilter, KeywordTitleFilter,
                 InMemoryEventPublisher, fetcher_registry.py,
                 FeedbackRepository, SalaryParser.

docs/            feedback.html — GitHub Pages static feedback UI

main.py          Wiring only — no business logic. Constructs objects, runs
                 fetcher pool, calls services, writes debug output, sends email.
```

---

## 14. All Numeric Constants and Thresholds

| Constant | Value | Location | What it controls |
|---|---|---|---|
| `MINIMUM_SCORE` | 5 | `domain/scoring_policy.py` | Score threshold to qualify |
| Core skill weight | 4 | `application/resume_profile_builder.py` | Points per core skill match |
| Secondary skill weight | 2 | `application/resume_profile_builder.py` | Points per secondary skill match |
| Tertiary skill weight | 1 | `application/resume_profile_builder.py` | Points per tertiary skill match |
| Missing skill penalty | −0.5 | `domain/scoring_policy.py` | Per required skill the candidate lacks (RemoteOK only) |
| `FEEDBACK_WEIGHT` | 0.5 | `domain/scoring_policy.py` | Multiplier for personal bias adjustment |
| Feedback signal threshold | 3 | `domain/scoring_policy.py` | Min net votes for a token to influence scoring |
| Feedback archive age | 90 days | `application/feedback_service.py` | Votes older than this are archived |
| Experience context window | 8 tokens | `domain/experience_requirement.py` | How far "experience" can be from the number |
| Experience max ignored | 20 years | `domain/experience_requirement.py` | Numbers above this are not treated as exp requirements |
| Moderate gap threshold | `ideal_max + 1` to `ideal_max + 4` | `domain/experience_requirement.py` | Both moderate and large gaps are filtered |
| Large gap threshold | `> ideal_max + 4` | `domain/experience_requirement.py` | |
| Fetcher timeout | 120 seconds | `main.py` | Per fetcher before skipping |
| Fetcher retries | 1 | `main.py` | Retries before marking fetcher as failed |
| Detail-page timeout | 12 seconds | Workday/iCIMS/AdzunaSimilar fetchers | Per job page HTTP request |
| Detail-page workers | 10 | Workday/iCIMS/AdzunaSimilar fetchers | Parallel threads for detail pages |
| Adzuna seed limit | 15 | `AdzunaSimilarFetcher` | How many seed pages to scrape for similar jobs |
| Score badge green | ≥ 11 | `infrastructure/email_notifier.py` | Green badge color |
| Score badge blue | ≥ 8 | `infrastructure/email_notifier.py` | Blue badge color |
| Score badge amber | ≥ 5 | `infrastructure/email_notifier.py` | Amber badge color |
| Gemini model | `gemini-2.0-flash-lite` | `infrastructure/llm_title_filter.py` | LLM used for title filtering |
| LLM temperature | 0 | `infrastructure/llm_title_filter.py` | Deterministic output |
| LLM timeout | 20 seconds | `infrastructure/llm_title_filter.py` | HTTP timeout for Gemini API |
| Landstar page size | 100 | `infrastructure/job_fetchers/landstar_fetcher.py` | Jobs per page |
| iCIMS scrape cap | 300 | `infrastructure/job_fetchers/icims_fetcher.py` | Max jobs from iCIMS HTML scrape |
| Weekly summary min votes | 20 | `application/feedback_service.py` | Min votes before weekly pattern summary appears |

---

## 15. Suggested Branch Structure

Work should be done in parallel across these feature branches, each merged to `main` by the
developer after review:

| Branch | Scope |
|---|---|
| `feature/scoring` | MINIMUM_SCORE, badge thresholds, skill penalty, salary filter, experience filter, employment type filter, location expansion, feedback-based scoring, personal bias map |
| `feature/fetchers` | JSearch, Netflix, Fanatics (both), Citi, JPMorgan, CSX, Florida Blue, Availity, remove 5 companies, AdzunaSimilar description scraping, retry logic, cron fix, detail page timeout, salary parsing |
| `feature/email` | Sort by score, always-send empty run email, failed fetcher section, possibly relevant passlist, debug JSON commit, run summary section, weekly pattern summary, missing key warnings |
| `feature/feedback` | feedback.json, GitHub Pages UI, repository_dispatch workflow, FeedbackService, archival logic, preset reason tags, CLAUDE.md + README updates |

Each branch must pass all tests and mypy before the developer merges it.

---

## 16. Known Limitations and Implicit Decisions

1. **`remote=False` is never set by any fetcher.** Every fetcher either sets `True` (confirmed
   remote) or `None` (unknown). This means the system never actually uses `remote=False` logic.

2. **Deduplication is global and permanent.** A job seen once is never shown again, even if its
   status changed. Delete `seen_jobs.json` to reset.

3. **Experience parsing reads only the first match.** If a description mentions experience
   requirements multiple times, only the first qualifying match is used.

4. **Scoring uses word-boundary matching.** `\bjava\b` matches "Java" but not "JavaScript".
   Multi-word skills like `"spring boot"` are matched as `\bspring boot\b`.

5. **No title normalization before scoring.** "Sr. Software Engineer" vs "Senior Software
   Engineer" are treated as different titles by the LLM filter.

6. **`open_to_contract=False` only catches `employment_type == "contract"` exactly.** Most
   fetchers set `None` for employment type when unknown.

7. **No geographic radius or commute logic.** Location matching is a simple substring check.

8. **LLM filter scope.** The Gemini prompt sends ALL post-filter titles in one call. No
   batching or chunking — could be a large prompt with many jobs.

9. **`AdzunaSimilarFetcher` now fetches descriptions** by following job URLs, but this adds
   latency. The 12-second detail-page timeout and 10 parallel workers mitigate this.

10. **CSX, Florida Blue, and Availity ATS are unverified.** Verify the ATS platform for each
    before implementing their fetchers. Check the careers page URL for `greenhouse.io`,
    `lever.co`, `myworkdayjobs.com`, `icims.com`, or other known patterns.

11. **JPMorgan Chase uses Oracle Cloud ATS** (`jpmc.fa.oraclecloud.com`). This requires a new
    `OracleFetcher` class — more development work than a standard Greenhouse/Lever/Workday
    fetcher.

12. **Fanatics posts on both Lever and Greenhouse.** The same job may appear from both fetchers.
    Deduplication handles this only if the job IDs are identical across both platforms — which
    they likely are not. Consider normalizing Fanatics job IDs by title+company hash as a
    secondary dedup key.

13. **No retry logic on the feedback webhook.** If the `repository_dispatch` call from the
    GitHub Pages UI fails, the vote is lost silently. Consider adding a visible error message
    on the feedback page.
