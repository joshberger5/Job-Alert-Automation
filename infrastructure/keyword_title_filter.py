from __future__ import annotations

from domain.candidate_profile import CandidateProfile
from application.job_record import JobRecord

# Lowercase substrings matched against job titles (case-insensitive).
# A title containing ANY of these fragments is rejected.
# Edit this list to add / remove role categories you know you're not a fit for.
_REJECTED_TITLE_FRAGMENTS: list[str] = [
    # ── Data / ML / Research ──────────────────────────────────────────────────
    "data scientist",
    "data engineer",
    "machine learning",
    "ml engineer",
    "research scientist",
    "research engineer",
    # ── Product / Design ──────────────────────────────────────────────────────
    "product manager",
    "product owner",
    "program manager",
    "ux designer",
    "ui designer",
    "product designer",
    "graphic designer",
    "visual designer",
    "interaction designer",
    # ── Finance / Legal / Accounting ──────────────────────────────────────────
    "financial analyst",
    "quantitative analyst",
    "quant analyst",
    "accountant",
    "economist",
    "attorney",
    "paralegal",
    "compliance officer",
    # ── People / Recruiting ───────────────────────────────────────────────────
    "recruiter",
    "talent acquisition",
    "human resources",
    # ── Sales / Marketing ─────────────────────────────────────────────────────
    "account executive",
    "account manager",
    "sales representative",
    "sales associate",
    "inside sales",
    "marketing manager",
    "marketing specialist",
    # ── Operations / Other ────────────────────────────────────────────────────
    "operations manager",
    "manual qa",
    "manual tester",
    "manual test",
]


class KeywordTitleFilter:
    """Fast local title filter — no API calls required.

    Rejects job records whose title contains any fragment from
    *rejected_fragments* (case-insensitive substring match).  Runs before
    the Gemini LLM filter so obvious non-fits never consume API quota.

    Mirrors the ``filter_by_title`` interface of ``GeminiTitleFilter`` so
    both can be used interchangeably in ``main.py``.
    """

    def __init__(
        self, rejected_fragments: list[str] | None = None
    ) -> None:
        self._fragments: list[str] = (
            rejected_fragments
            if rejected_fragments is not None
            else _REJECTED_TITLE_FRAGMENTS
        )

    def filter_by_title(
        self, records: list[JobRecord], profile: CandidateProfile
    ) -> set[str]:
        """Return the set of job IDs whose titles do not match any rejected fragment."""
        approved_ids: set[str] = set()
        rejected_count: int = 0

        for record in records:
            title_lower: str = record["title"].lower()
            if any(frag in title_lower for frag in self._fragments):
                rejected_count += 1
            else:
                approved_ids.add(record["id"])

        print(
            f"  [KeywordFilter] {len(approved_ids)} approved, "
            f"{rejected_count} rejected by title keyword"
        )
        return approved_ids
