---
phase: 01-scoring-and-profile
plan: "03"
subsystem: domain
tags: [filtering, salary, candidate-profile, scoring-policy]

requires:
  - phase: 01-02
    provides: minimum_salary field on CandidateProfile

provides:
  - Salary floor filter in FilteringPolicy.allows() (check 1.5)
  - minimum_salary field on CandidateProfile (prerequisite applied on feature/scoring)
  - 4 new salary-filter test cases in test_filtering_policy.py

affects:
  - 01-04
  - downstream plans that rely on FilteringPolicy behavior

tech-stack:
  added: []
  patterns:
    - "Fail-open on missing data: salary=None always passes salary filter"
    - "Skip-when-zero: minimum_salary=0 disables the entire salary check"
    - "Inline check ordering: salary filter inserted as 1.5 between contract (1) and experience gap (2)"

key-files:
  created: []
  modified:
    - domain/candidate_profile.py
    - domain/filtering_policy.py
    - tests/test_filtering_policy.py

key-decisions:
  - "Use explicit `salary_range.maximum is not None and salary_range.maximum < profile.minimum_salary` rather than meets_minimum() to preserve fail-open behavior when salary is unknown"
  - "minimum_salary=0 means no salary filtering (disabled by default) — matches Plan 02 design"
  - "Salary check positioned as 1.5 — after contract (fast exit) but before experience gap (regex scan) for efficiency"
  - "Applied minimum_salary prerequisite from Plan 02 directly on feature/scoring branch since gsd branch changes hadn't been merged"

patterns-established:
  - "Salary filter: check profile.minimum_salary > 0 first, then check salary_range.maximum is not None, then compare"

requirements-completed:
  - SCORE-02

duration: 12min
completed: 2026-03-11
---

# Phase 01 Plan 03: Salary Floor Filter Summary

**Salary floor filter added to FilteringPolicy.allows() between contract and experience-gap checks, with fail-open behavior for jobs missing salary data**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-11T21:15:00Z
- **Completed:** 2026-03-11T21:27:00Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments

- Added `minimum_salary: int = 0` field to CandidateProfile (prerequisite from Plan 02, applied on feature/scoring)
- Inserted salary floor check (1.5) in FilteringPolicy.allows() — rejects job when salary_max is known and below minimum_salary
- Fail-open: jobs with salary=None always pass (no salary listed = do not filter)
- 4 new test cases covering all salary filter edge cases — all 113 tests pass

## Task Commits

1. **Task 1a: Salary floor implementation** - `7c4e57a` (feat)
2. **Task 1b: Salary filter tests** - `9093648` (test)

## Files Created/Modified

- `domain/candidate_profile.py` - Added `minimum_salary: int = 0` and feedback reason fields
- `domain/filtering_policy.py` - Added `SalaryRange` import; added salary floor filter at check 1.5
- `tests/test_filtering_policy.py` - Added `minimum_salary` param to `_make_profile()`, `salary` param to `_make_job()`, 4 new salary test functions

## Decisions Made

- Used explicit `salary_range.maximum is not None and salary_range.maximum < profile.minimum_salary` instead of `salary_range.meets_minimum()` — the `meets_minimum()` method returns `False` when `maximum is None`, which would incorrectly filter jobs with no listed salary (violates fail-open requirement)
- Salary check runs before experience gap check (check 2) for efficiency: salary string parse is O(1), experience scan uses regex over full description
- `minimum_salary=0` (the default) disables the salary filter entirely — consistent with Plan 02 design intent

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Applied Plan 02 prerequisite (minimum_salary) directly on feature/scoring**

- **Found during:** Task 1 setup
- **Issue:** `minimum_salary` field was added to CandidateProfile on `gsd/phase-01-scoring-and-profile` (Plans 01/02), but `feature/scoring` (the target branch per CLAUDE.md) did not have it. Plan 03 `depends_on: ["01-02"]` — the dependency hadn't been applied to the working branch.
- **Fix:** Applied the `minimum_salary: int = 0` and feedback reason fields directly to `domain/candidate_profile.py` on `feature/scoring`
- **Files modified:** `domain/candidate_profile.py`
- **Verification:** All 113 tests pass, mypy clean
- **Committed in:** `7c4e57a` (Task 1 feat commit)

---

**Total deviations:** 1 auto-fixed (1 blocking prerequisite)
**Impact on plan:** Required for the salary filter to compile and run. No scope creep.

## Issues Encountered

None beyond the prerequisite branch discrepancy documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- FilteringPolicy now enforces salary floor when `minimum_salary > 0` in candidate_profile.yaml
- All downstream plans that test FilteringPolicy can pass `minimum_salary` to `_make_profile()` helper
- Plan 04 (taxonomy/scoring) can proceed independently

---
*Phase: 01-scoring-and-profile*
*Completed: 2026-03-11*
