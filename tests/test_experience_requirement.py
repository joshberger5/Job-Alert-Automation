from domain.experience_alignment import ExperienceAlignment
from domain.experience_requirement import ExperienceRequirement


def _req(text: str) -> ExperienceRequirement:
    return ExperienceRequirement.from_job_content(text)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_parses_years_experience() -> None:
    req: ExperienceRequirement = _req("Requires 5 years experience in Java.")
    assert req.required_years == 5


def test_parses_years_with_trailing_punctuation() -> None:
    """Comma after "years" should still parse correctly."""
    req: ExperienceRequirement = _req("We want 3 years, experience with Python.")
    assert req.required_years == 3


def test_parses_plus_suffix() -> None:
    """'5+' should extract 5."""
    req: ExperienceRequirement = _req("5+ years of experience required.")
    assert req.required_years == 5


def test_no_experience_phrase_returns_none() -> None:
    req: ExperienceRequirement = _req("No requirements mentioned here.")
    assert req.required_years is None


def test_no_experience_phrase_aligns_unknown() -> None:
    req: ExperienceRequirement = _req("No requirements mentioned here.")
    assert req.alignment_with(3) == ExperienceAlignment.UNKNOWN


# ---------------------------------------------------------------------------
# Alignment
# ---------------------------------------------------------------------------


def test_within_ideal_range() -> None:
    """3 years required vs ideal_max=3 → WITHIN_IDEAL_RANGE."""
    req: ExperienceRequirement = _req("3 years experience needed.")
    assert req.alignment_with(3) == ExperienceAlignment.WITHIN_IDEAL_RANGE


def test_within_ideal_range_below_max() -> None:
    """2 years required vs ideal_max=3 → WITHIN_IDEAL_RANGE."""
    req: ExperienceRequirement = _req("2 years experience preferred.")
    assert req.alignment_with(3) == ExperienceAlignment.WITHIN_IDEAL_RANGE


def test_moderate_gap() -> None:
    """4 years required vs ideal_max=3 → MODERATE_GAP (4 ≤ 3+4)."""
    req: ExperienceRequirement = _req("4 years experience required.")
    assert req.alignment_with(3) == ExperienceAlignment.MODERATE_GAP


def test_moderate_gap_upper_bound() -> None:
    """7 years required vs ideal_max=3 → MODERATE_GAP (7 ≤ 3+4)."""
    req: ExperienceRequirement = _req("7 years experience required.")
    assert req.alignment_with(3) == ExperienceAlignment.MODERATE_GAP


def test_large_gap() -> None:
    """8 years required vs ideal_max=3 → LARGE_GAP (8 > 3+4)."""
    req: ExperienceRequirement = _req("8 years experience required.")
    assert req.alignment_with(3) == ExperienceAlignment.LARGE_GAP


# ---------------------------------------------------------------------------
# SCORE-05: boundary cases — ideal_max+5 and ideal_max+3
# ---------------------------------------------------------------------------


def test_large_gap_when_required_is_ideal_max_plus_five() -> None:
    """8 years required vs ideal_max=3 (ideal_max+5=8 > 3+4=7) → LARGE_GAP."""
    req: ExperienceRequirement = ExperienceRequirement(required_years=8)
    assert req.alignment_with(3) == ExperienceAlignment.LARGE_GAP


def test_moderate_gap_when_required_is_ideal_max_plus_three() -> None:
    """6 years required vs ideal_max=3 (ideal_max+3=6 <= 3+4=7) → MODERATE_GAP."""
    req: ExperienceRequirement = ExperienceRequirement(required_years=6)
    assert req.alignment_with(3) == ExperienceAlignment.MODERATE_GAP
