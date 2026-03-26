from __future__ import annotations

from domain.candidate_profile import CandidateProfile
from application.job_record import JobRecord

# Lowercase substrings matched against job titles (case-insensitive).
# A title containing ANY of these fragments is rejected.
# The whitelist below can override these — use for role-type rejections.
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
    "product development",
    "program manager",
    "ux designer",
    "ui designer",
    "product designer",
    "graphic designer",
    "visual designer",
    "interaction designer",
    # ── Finance / Legal / Accounting ──────────────────────────────────────────
    "financial analyst",
    "financial advisor",
    "quantitative analyst",
    "quant analyst",
    "accountant",
    "economist",
    "attorney",
    "paralegal",
    "compliance officer",
    "tax resolution",
    "account management",
    "wealth management",
    "transaction management",
    # ── People / Recruiting ───────────────────────────────────────────────────
    "recruiter",
    "talent acquisition",
    "human resources",
    # ── Banking / Insurance ────────────────────────────────────────────────────
    "relationship banker",
    "insurance agent",
    # ── Sales / Marketing ─────────────────────────────────────────────────────
    "account executive",
    "account manager",
    "sales executive",
    "sales representative",
    "sales associate",
    "inside sales",
    "marketing manager",
    "marketing specialist",
    "sales solution",
    "customer acquisition",
    "institutional sales",
    # ── Operations / Other ────────────────────────────────────────────────────
    "operations manager",
    "ops analyst",
    "manual qa",
    "manual tester",
    "manual test",
    "program and operations manager",
    # ── Non-SWE engineering roles ─────────────────────────────────────────────
    "site reliability",
    "solutions engineer",
    "data analyst",
    "test infrastructure",
    "civil engineering",
    "business development",
    "electrical design",
    "risk analyst",
    "support agent",
    "front-end developer",
    "frontend developer",
    # ── Legal roles ───────────────────────────────────────────────────────────
    "senior counsel",
    "counsel",
    # ── Management roles ──────────────────────────────────────────────────────
    "engineering manager",
    "technical program management",
    "program management",
    "technical product owner",
    "technical program manager",
    "technical product manager",
    "solutions architect, manager",
    "assistant vice president",
    "vice president",
    "security manager",
    "devops lead",
    "application development manager",
]

# Seniority-based rejections — whitelist cannot override these.
# Use for levels that are structurally out of range regardless of role type.
_HARD_REJECTED_TITLE_FRAGMENTS: list[str] = [
    "staff software engineer",  # typically 6-8+ yrs; candidate has ~2
    "staff engineer",           # covers staff titles more broadly
    "principal software",       # above staff
]

# Lowercase substrings matched against job titles (case-insensitive).
# A title matching ANY of these fragments is approved immediately,
# overriding role-type rejections (but NOT hard/seniority rejections).
_WHITELISTED_TITLE_FRAGMENTS: list[str] = [
    "software engineer, backend",
    "backend software engineer",
]


class KeywordTitleFilter:
    """Fast local title filter — no API calls required.

    Evaluation order per title:
      1. Hard reject (seniority) → always reject; whitelist cannot override.
      2. Whitelist → approve immediately; overrides role-type rejections.
      3. Role-type reject → reject.
      4. Default → approve.

    Mirrors the ``filter_by_title`` interface of ``GeminiTitleFilter`` so
    both can be used interchangeably in ``main.py``.
    """

    def __init__(
        self,
        rejected_fragments: list[str] | None = None,
        hard_rejected_fragments: list[str] | None = None,
        whitelisted_fragments: list[str] | None = None,
    ) -> None:
        self._fragments: list[str] = (
            rejected_fragments
            if rejected_fragments is not None
            else _REJECTED_TITLE_FRAGMENTS
        )
        self._hard_rejected: list[str] = (
            hard_rejected_fragments
            if hard_rejected_fragments is not None
            else _HARD_REJECTED_TITLE_FRAGMENTS
        )
        self._whitelisted: list[str] = (
            whitelisted_fragments
            if whitelisted_fragments is not None
            else _WHITELISTED_TITLE_FRAGMENTS
        )

    def filter_by_title(
        self, records: list[JobRecord], profile: CandidateProfile
    ) -> set[str]:
        """Return the set of job IDs whose titles do not match any rejected fragment."""
        approved_ids: set[str] = set()
        rejected_count: int = 0

        for record in records:
            title_lower: str = record["title"].lower()
            if any(frag in title_lower for frag in self._hard_rejected):
                rejected_count += 1
            elif any(frag in title_lower for frag in self._whitelisted):
                approved_ids.add(record["id"])
            elif any(frag in title_lower for frag in self._fragments):
                rejected_count += 1
            else:
                approved_ids.add(record["id"])

        print(
            f"  [KeywordFilter] {len(approved_ids)} approved, "
            f"{rejected_count} rejected by title keyword"
        )
        return approved_ids
