---
phase: 01-scoring-and-profile
plan: 05
subsystem: scoring
tags: [feedback, bias, multiplier, scoring, job-processing]

# Dependency graph
requires:
  - phase: 01-scoring-and-profile/01-01
    provides: CandidateProfile, ScoringPolicy infrastructure used by JobProcessingService
  - phase: 01-scoring-and-profile/01-02
    provides: JobRecord TypedDict extended here with feedback_multiplier field

provides:
  - FeedbackBiasService with multiplier algorithm (SCORE-04)
  - feedback_multiplier float field on JobRecord
  - FeedbackBiasService injected into JobProcessingService
  - 9 GREEN tests covering all SCORE-04 multiplier behaviors

affects:
  - Phase 3 (FEED-04): FeedbackBiasService reads feedback.json written by Phase 3's feedback system

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Optional service injection with default fallback in __init__ (FeedbackBiasService | None = None)
    - Fail-open pattern: missing/malformed feedback.json returns empty bias_map, multiplier stays 1.0
    - Word-boundary regex matching for token lookup in job content (case-insensitive)

key-files:
  created:
    - application/feedback_bias_service.py
    - tests/test_feedback_bias_service.py
  modified:
    - application/job_record.py
    - application/job_processing_service.py
    - main.py
    - tests/test_job_processing_service.py

key-decisions:
  - "FeedbackBiasService.apply() returns 3-tuple (final_score, breakdown, clamped_multiplier) so callers get multiplier for JobRecord storage without a second call"
  - "feedback_score_delta stored as int in breakdown dict[str, int] — avoids float leaking into breakdown type"
  - "FeedbackBiasService defaults to FeedbackBiasService() in JobProcessingService.__init__() for backward compatibility — existing callers need no changes"
  - "vote_raw cast via float(str(vote_raw)) before int() to satisfy mypy strict mode without type: ignore"

patterns-established:
  - "Fail-open: any I/O or parse error in _load_bias_map returns {} so scoring continues unaffected"
  - "Multiplier clamping at [0.5, 2.0]: prevents both score zeroing and runaway amplification"

requirements-completed: [SCORE-04]

# Metrics
duration: 12min
completed: 2026-03-11
---

# Phase 1 Plan 05: FeedbackBiasService — Multiplier-Based Score Adjustment Summary

**FeedbackBiasService reads feedback.json vote history to compute a per-job multiplier (clamped [0.5, 2.0]) applied after ScoringPolicy.evaluate(), with feedback_multiplier visible in jobs_debug.json**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-11T21:23:00Z
- **Completed:** 2026-03-11T21:35:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- New `application/feedback_bias_service.py`: FeedbackBiasService with bias_map loading, threshold filtering (|net| >= 3), word-boundary token matching, and multiplier clamping to [0.5, 2.0]
- `JobRecord` gains `feedback_multiplier: float` optional field; `JobProcessingService` sets it on every scored record
- `main.py` constructs `FeedbackBiasService()` at startup and passes it to `JobProcessingService`
- 9 new GREEN tests in `test_feedback_bias_service.py`; 1 new integration test in `test_job_processing_service.py`; full suite 129 passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement FeedbackBiasService and add feedback_multiplier to JobRecord** - `adcd5a3` (feat)
2. **Task 2: Wire FeedbackBiasService into JobProcessingService and main.py** - `b989dce` (feat)

**Plan metadata:** (docs commit below)

_Note: TDD tasks each include tests and implementation in the same commit per plan specification_

## Files Created/Modified
- `application/feedback_bias_service.py` - FeedbackBiasService with FEEDBACK_WEIGHT=0.5, threshold=3, clamped multiplier
- `application/job_record.py` - Added `feedback_multiplier: float` optional field
- `application/job_processing_service.py` - Import + inject FeedbackBiasService; apply() called after ScoringPolicy.evaluate()
- `main.py` - Import FeedbackBiasService; pass instance to JobProcessingService constructor
- `tests/test_feedback_bias_service.py` - 9 tests covering no-file, below-threshold, at-threshold, clamp min/max, delta in breakdown, no content match, parse error, vote normalization
- `tests/test_job_processing_service.py` - 1 new test: scored records have feedback_multiplier float

## Decisions Made
- `apply()` returns 3-tuple `(final_score, breakdown, clamped_multiplier)` so the multiplier is accessible for `JobRecord` storage without a second call or property access
- `feedback_score_delta` stored as `int` in `dict[str, int]` — avoids float pollution in the score breakdown type
- `FeedbackBiasService` defaults to `FeedbackBiasService()` in `JobProcessingService.__init__()` for backward compatibility; all existing callers continue to work unmodified
- Vote normalization uses `float(str(vote_raw))` then `int()` to satisfy mypy strict mode without `# type: ignore` hacks

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mypy type error on vote_raw cast**
- **Found during:** Task 1 (implement FeedbackBiasService)
- **Issue:** `int(vote_raw)` where `vote_raw: object` fails mypy's call-overload check; original plan used `# type: ignore[arg-type]` which was itself flagged as "unused-ignore" in this Python version
- **Fix:** Changed to `float(str(vote_raw))` then `int()` — fully type-safe, no ignores needed
- **Files modified:** `application/feedback_bias_service.py`
- **Verification:** `py -m mypy .` reports "no issues found in 60 source files"
- **Committed in:** adcd5a3 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Required to satisfy mypy strict mode; no behavioral change.

## Issues Encountered
None — plan executed cleanly after the mypy cast fix.

## User Setup Required
None - no external service configuration required. FeedbackBiasService reads `feedback.json` at runtime; the file is optional (fail-open when absent).

## Next Phase Readiness
- `FeedbackBiasService` is ready to consume `feedback.json` once Phase 3 (feedback system) writes it
- `feedback_multiplier` field is visible in `jobs_debug.json` on every scored record
- All SCORE-04 requirements satisfied

---
*Phase: 01-scoring-and-profile*
*Completed: 2026-03-11*

## Self-Check: PASSED

- FOUND: application/feedback_bias_service.py
- FOUND: application/job_record.py
- FOUND: tests/test_feedback_bias_service.py
- FOUND: commit adcd5a3
- FOUND: commit b989dce
