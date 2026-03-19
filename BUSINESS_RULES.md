# Business Rules

This document is the authoritative spec for all filtering, scoring, and email
rendering behavior. Every PR that touches these areas must verify compliance.
Claude must check this document before opening any PR.

---

## 1. Job Filtering

### 1.1 Remote Check
The remote check uses BOTH `job.remote` (set by fetcher) AND `infer_remote(location)`.
A job is treated as remote if `job.remote is True` OR `infer_remote(location) returns True`.

A remote job passes the remote check if:
- The combined remote signal is True, AND
- The location is US-accessible (`_is_globally_or_us_remote`), AND
- Neither the location nor description contains `"hybrid"` or `"in-office"`

US-accessible means: strip the word "remote" from the location string, then check
if any remaining word is in `{"us", "usa", "united", "states", "america",
"worldwide", "global", "anywhere"}`. A location of purely `"Remote"` (nothing
else after stripping) also passes.

A specific city+country location (e.g. `"New York, United States"`) passes the
US-accessible check. It is only rejected if `"hybrid"` or `"in-office"` appears
in the description or location.

### 1.2 Unverified Remote
A job is unverified remote if:
- It does NOT pass `FilteringPolicy.allows()`, AND
- The job description mentions an explicit remote-work phrase (e.g. "fully remote",
  "100% remote", "work from home", "remote work environment")

Unverified remote jobs are scored, run through the title filter, and shown in the
**Unverified Remote** email section. They are saved to `seen_jobs.json` with
`result = "unverified_remote"`.

### 1.3 Location Match
A job passes the location check if any string in `profile.preferred_locations`
appears as a substring (case-insensitive) in `job.location`.

### 1.4 Remote/Location Logic
Remote check and location check are OR conditions — a job passes filtering if it
satisfies either one.

### 1.5 Other Filters (applied before remote/location)
- **Contract filter:** rejected when `profile.open_to_contract is False` and
  `job.employment_type == "contract"`
- **Salary floor:** rejected when the job's salary maximum is known and is below
  `profile.minimum_salary`. Missing or unparseable salary = fail-open (allowed).
- **Experience gap:** rejected when the required years of experience creates a
  MODERATE_GAP or LARGE_GAP relative to `profile.ideal_max_experience_years`.
  Skipped entirely when `ideal_max_experience_years == 0` (less than 12 months
  total experience on resume).

---

## 2. Scoring

- Minimum qualifying score: `ScoringPolicy.MINIMUM_SCORE = 7` (inclusive — `>= 7` qualifies)
- Score is computed by `ScoringPolicy.evaluate()` which returns `(score, breakdown)`
- Feedback bias is applied after base scoring — the threshold check runs on the
  **final score** (base + bias). Bias can promote `scored_out` → `qualified` or
  demote `qualified` → `scored_out`.
- A job with `final_score >= MINIMUM_SCORE` is `result = "qualified"`
- A job with `final_score < MINIMUM_SCORE` (but passed filtering) is
  `result = "scored_out"`

### 2.1 Feedback Bias
- Feedback archival runs **before** the main pipeline so scoring uses the
  already-trimmed `feedback.json`
- Only tokens with `|net_vote_score| >= 3` across all feedback records influence scoring
- Net vote score is calculated per token across all feedback records

---

## 3. Title Filter

The title filter runs on **every job that will appear in the email** — including
unverified remote jobs. Any job whose title matches the keyword blocklist is
`result = "title_filtered"` and never appears in any email section.

### 3.1 Keyword Blocklist (always runs)
Fast, local, no API calls. See `infrastructure/keyword_title_filter.py` for the
full list.

Effect: any job (`qualified`, `scored_out`, or `unverified_remote`) whose title
matches → `result = "title_filtered"`.

### 3.2 LLM Filter (optional, requires `GEMINI_API_KEY`)
Runs on jobs that passed the keyword filter.

`llm_result` field values:
- `"approved"` — LLM said keep it
- `"rejected"` — LLM said filter it (→ `result = "title_filtered"`)
- `"skipped"` — LLM not run (no API key, API error, or quota exhausted)

**Fails open:** on any API error, all jobs in the batch get `llm_result = "skipped"`.
Jobs with `llm_result = "skipped"` still appear in Possibly Relevant if they
match the passlist.

---

## 4. Email Sections

The email always renders all sections, even when empty. All sections use the
same score badge thresholds. Jobs within each section are sorted by score descending.

| Section | Criteria |
|---|---|
| **Qualified Jobs** | `result == "qualified"` |
| **Possibly Relevant** | `result == "scored_out"` AND (matches title passlist OR `llm_result == "approved"`) |
| **Filtered by Title** | `result == "title_filtered"` — always shown, even without `GEMINI_API_KEY` |
| **Unverified Remote** | `result == "unverified_remote"` |
| **Run Log** | Full stdout+stderr capture — everything printed during the run |

### 4.1 Score Badges
Universal across all email sections:
- `>= 11` — Navy `#1E3A8A`
- `>= 8` — Blue `#2563EB`
- `>= 7` — Slate `#64748B`

### 4.2 Weekly Pattern Summary
Shown once per week on the first run of Monday (ET timezone). Only appears when
`feedback.json` contains >= 20 votes. Analyzes thumbs-down patterns and suggests
blocklist additions.

---

## 5. Vote Links

- Vote links appear on job cards only when `FEEDBACK_PAT` env var is set AND
  the job has a non-empty `id`
- The PAT is placed in the URL **fragment** (`#token`), never as a query
  parameter — this keeps it out of server and proxy logs
- Both 👍 (Relevant) and 👎 (Not relevant) links must have explicit color
  styling set (`color:#3b82f6` for relevant, `color:#64748b` for not relevant)
- Vote link icons must be rendered as `<img>` elements (not inline SVG) for
  email client compatibility

---

## 6. Feedback System

- `feedback.json` is capped at 50 records; oldest trimmed when exceeded
- Trimming logic exists in two places — keep them in sync:
  - `infrastructure/feedback_trimmer.py` (unit-tested)
  - Inline Python step in `feedback.yml` (runs in CI)
- `docs/feedback.html` uses `__THUMBS_UP_REASONS__` and
  `__THUMBS_DOWN_REASONS__` placeholders — never hardcode reasons in the HTML
- Votes older than 90 days are archived to `feedback_archive_YYYY_MM.json`
  **before** the main pipeline runs

---

## 7. Email Archiving

- After every run, `archive_email()` writes `docs/emails/email_YYYYMMDD_HHMMSS.html`
- Maximum 5 archived files; oldest is deleted when the cap is exceeded
- Archiving runs unconditionally (even when SMTP is not configured)
- The `FEEDBACK_PAT` is replaced with `[REDACTED]` in archived files — the live
  email sent via SMTP retains working vote links; the git-committed copy does not

---

## 8. Persistence

### 8.1 seen_jobs.json
- Stores every job processed (excluding duplicates and filtered-out jobs)
- Record format: `{job_id: {first_seen, score, result}}`
- `result` values: `"qualified"`, `"scored_out"`, `"unverified_remote"`, `"title_filtered"`
- A hash of `candidate_profile.yaml` + resume is stored alongside records. If the
  hash changes on startup, `seen_jobs.json` is automatically deleted, the run
  proceeds fresh, and the reset is logged prominently in the run log and email.

### 8.2 jobs_debug.json
- Cumulative, human-read only — never read by the system
- Appended each run; entries older than 30 days are pruned at run start
- Contains full metadata, score breakdown, and result for every job

---

## 9. Fetcher Conventions

- `job.remote = True` — confirmed remote (fetcher has positive evidence)
- `job.remote = None` — unknown (default; filter uses `infer_remote(location)`)
- `job.remote = False` — confirmed on-site (only when fetcher has definitive evidence)
- All salary parsing goes through `SalaryParser` — never inline in fetchers
- Register new fetchers in `infrastructure/fetcher_registry.py`
- Each fetcher gets one immediate retry on failure before being marked failed
- Partial results from a timed-out fetcher are kept
- Failed fetcher output (error + traceback) is always included in the run log

### 9.1 Fetcher Health
- Consecutive failure counts tracked in `fetcher_health.json`
- After 3 consecutive failures, a GitHub Actions workflow runs Claude Code
  non-interactively to diagnose and attempt a fix, then opens a PR for review
- On a successful run, the fetcher's consecutive failure count resets to 0
- If the repair workflow is unavailable, fall back to a loud alert in the email
  with the full traceback
