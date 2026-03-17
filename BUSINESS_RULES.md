# Business Rules

This document is the authoritative spec for all filtering, scoring, and email
rendering behavior. Every PR that touches these areas must verify compliance.
Claude must check this document before opening any PR.

---

## 1. Job Filtering

### 1.1 Confirmed Remote
A job is confirmed remote (passes the remote check) if **either**:
- `job.remote is True` (fetcher explicitly marked it remote) AND the location is
  US/globally accessible (`_is_globally_or_us_remote`)
- `job.remote is None` AND the **location string itself** contains the word
  `"remote"` OR an unambiguous global word (`worldwide`, `global`, `anywhere`),
  AND `_is_globally_or_us_remote` returns True

**Rule:** A US city appearing in the location (e.g. `"New York, United States"`)
does NOT make a job confirmed remote, even if the job description mentions remote
work. `"United States"` in a city address must never be treated as a remote
indicator.

### 1.2 Unverified Remote
A job is unverified remote if:
- It does NOT pass `FilteringPolicy.allows()`, AND
- The job description mentions an explicit remote-work phrase (e.g. "fully remote",
  "100% remote", "work from home", "remote work environment")

Unverified remote jobs are **scored** and shown in the **Unverified Remote**
email section. They are saved to `seen_jobs.json` (so they don't repeat every run)
but are never marked as qualified.

### 1.3 Location Match
A job passes the location check if any string in `profile.preferred_locations`
appears as a substring (case-insensitive) in `job.location`.

### 1.4 Other Filters (applied before remote/location)
- **Contract filter:** rejected when `profile.open_to_contract is False` and
  `job.employment_type == "contract"`
- **Salary floor:** rejected when the job's salary maximum is known and is below
  `profile.minimum_salary`. Missing salary = fail-open (allowed).
- **Experience gap:** rejected when the required years of experience creates a
  MODERATE_GAP or LARGE_GAP relative to `profile.ideal_max_experience_years`.

---

## 2. Scoring

- Minimum qualifying score: `ScoringPolicy.MINIMUM_SCORE = 7`
- Score is computed by `ScoringPolicy.evaluate()` which returns `(score, breakdown)`
- Feedback bias is applied multiplicatively via `FeedbackBiasService`
- A job with `final_score >= MINIMUM_SCORE` is `result = "qualified"`
- A job with `final_score < MINIMUM_SCORE` (but passed filtering) is
  `result = "scored_out"`

---

## 3. Deduplication

- A job is a duplicate if `repository.exists(job.id)` returns True
- Duplicate jobs are skipped entirely (not scored, not saved again)
- Note: Fanatics posts on both Lever and Greenhouse with different IDs —
  standard dedup won't catch cross-platform duplicates for the same posting

---

## 4. Email Sections

The email always renders all sections, even when empty.

| Section | Source | Criteria |
|---|---|---|
| **Qualified Jobs** | `records` | `result == "qualified"` |
| **LLM Rejected** | `records` (post title-filter) | `result == "llm_filtered"` |
| **Possibly Relevant** | `records` (post title-filter) | `result == "scored_out"` AND `llm_relevant == True` |
| **Unverified Remote** | `records` | `result == "unverified_remote"` |
| **Run Log** | stdout capture | Always present |

Jobs within each section are sorted by score descending.

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

- `feedback.json` is capped at 50 records
- Trimming logic exists in two places — keep them in sync:
  - `infrastructure/feedback_trimmer.py` (unit-tested)
  - Inline Python step in `feedback.yml` (runs in CI)
- `docs/feedback.html` uses `__THUMBS_UP_REASONS__` and
  `__THUMBS_DOWN_REASONS__` placeholders — never hardcode reasons in the HTML

---

## 7. Email Archiving

- After every run, `archive_email()` writes `docs/emails/email_YYYYMMDD_HHMMSS.html`
- Maximum 5 archived files; oldest is deleted when the cap is exceeded
- Archiving runs unconditionally (even when SMTP is not configured)

---

## 8. Fetcher Conventions

- `job.remote = True` — confirmed remote (fetcher has positive evidence)
- `job.remote = None` — unknown (default; use `infer_remote(location)`)
- `job.remote = False` — confirmed on-site (only when fetcher has definitive evidence)
- All salary parsing goes through `SalaryParser` — never inline in fetchers
- Register new fetchers in `infrastructure/fetcher_registry.py`
