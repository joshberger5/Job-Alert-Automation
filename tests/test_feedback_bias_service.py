"""
Failing test stubs (RED phase) for FeedbackBiasService behavioral contracts.

Covers:
  SCORE-04: feedback multiplier logic — threshold, clamping, and no-file behavior.

These tests WILL fail with ModuleNotFoundError until Plan 05 implements
application/feedback_bias_service.py. That is the correct RED state.
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# FeedbackBiasService does not exist until Plan 05.
# Wrapping in try/except allows pytest to collect other test files without aborting.
try:
    from application.feedback_bias_service import FeedbackBiasService  # type: ignore[import-not-found]
    _IMPORT_ERROR: ImportError | None = None
except ImportError as _exc:
    _IMPORT_ERROR = _exc

    class FeedbackBiasService:  # type: ignore[no-redef]
        """Placeholder so test bodies can reference the name without crashing collection."""
        pass

# ---------------------------------------------------------------------------
# Import guard — fail each test (not the whole collection) when module missing
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _require_import() -> None:
    """Skip/fail every test in this file if FeedbackBiasService was not importable."""
    if _IMPORT_ERROR is not None:
        pytest.fail(
            f"application.feedback_bias_service not implemented yet (Plan 05): {_IMPORT_ERROR}"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_feedback(tmp_path: Path, entries: list[dict[str, Any]]) -> Path:
    """Write a feedback JSON file and return its path."""
    feedback_file: Path = tmp_path / "feedback.json"
    feedback_file.write_text(json.dumps(entries))
    return feedback_file


def _entry(vote: str, reason: str) -> dict[str, Any]:
    """Build a minimal feedback entry."""
    return {
        "job_id": "1",
        "title": "Software Engineer",
        "company": "Acme",
        "vote": vote,
        "reason": reason,
        "voted_at": "2026-01-01",
    }


# ---------------------------------------------------------------------------
# SCORE-04: FeedbackBiasService behavioral contracts
# ---------------------------------------------------------------------------


def test_multiplier_is_one_when_no_feedback_file(tmp_path: Path) -> None:
    """When no feedback.json exists, apply() should return the base score unchanged."""
    missing_path: Path = tmp_path / "nonexistent_feedback.json"
    with patch("application.feedback_bias_service._FEEDBACK_PATH", missing_path):
        service: FeedbackBiasService = FeedbackBiasService()
        result_score: int
        result_breakdown: dict[str, int]
        result_score, result_breakdown = service.apply(
            base_score=10,
            job_content="java developer",
            base_breakdown={},
        )
    assert result_score == 10


def test_token_below_threshold_does_not_contribute(tmp_path: Path) -> None:
    """Token with net_votes=2 (below threshold of 3) should not affect the score."""
    # 2 positive votes for "java" = net_votes 2, below threshold 3
    entries: list[dict[str, Any]] = [
        _entry("+1", "java"),
        _entry("+1", "java"),
    ]
    feedback_file: Path = _write_feedback(tmp_path, entries)
    with patch("application.feedback_bias_service._FEEDBACK_PATH", feedback_file):
        service: FeedbackBiasService = FeedbackBiasService()
        result_score: int
        result_breakdown: dict[str, int]
        result_score, result_breakdown = service.apply(
            base_score=10,
            job_content="java developer",
            base_breakdown={},
        )
    assert result_score == 10


def test_token_at_threshold_contributes(tmp_path: Path) -> None:
    """Token with net_votes=3 (at threshold) should cause the score to change."""
    # 3 positive votes for "java" = net_votes 3, at threshold
    entries: list[dict[str, Any]] = [
        _entry("+1", "java"),
        _entry("+1", "java"),
        _entry("+1", "java"),
    ]
    feedback_file: Path = _write_feedback(tmp_path, entries)
    base_score: int = 10
    with patch("application.feedback_bias_service._FEEDBACK_PATH", feedback_file):
        service: FeedbackBiasService = FeedbackBiasService()
        result_score: int
        result_breakdown: dict[str, int]
        result_score, result_breakdown = service.apply(
            base_score=base_score,
            job_content="java developer",
            base_breakdown={},
        )
    assert result_score != base_score


def test_multiplier_clamped_at_minimum(tmp_path: Path) -> None:
    """Strong negative feedback must not drive final score below round(base * 0.5)."""
    # Many strong negative votes for "java" (appears in job)
    entries: list[dict[str, Any]] = [_entry("-1", "java") for _ in range(20)]
    feedback_file: Path = _write_feedback(tmp_path, entries)
    base_score: int = 10
    min_expected: int = round(base_score * 0.5)
    with patch("application.feedback_bias_service._FEEDBACK_PATH", feedback_file):
        service: FeedbackBiasService = FeedbackBiasService()
        result_score: int
        result_breakdown: dict[str, int]
        result_score, result_breakdown = service.apply(
            base_score=base_score,
            job_content="java developer",
            base_breakdown={},
        )
    assert result_score >= min_expected


def test_multiplier_clamped_at_maximum(tmp_path: Path) -> None:
    """Strong positive feedback must not drive final score above round(base * 2.0)."""
    # Many strong positive votes for "java" (appears in job)
    entries: list[dict[str, Any]] = [_entry("+1", "java") for _ in range(20)]
    feedback_file: Path = _write_feedback(tmp_path, entries)
    base_score: int = 10
    max_expected: int = round(base_score * 2.0)
    with patch("application.feedback_bias_service._FEEDBACK_PATH", feedback_file):
        service: FeedbackBiasService = FeedbackBiasService()
        result_score: int
        result_breakdown: dict[str, int]
        result_score, result_breakdown = service.apply(
            base_score=base_score,
            job_content="java developer",
            base_breakdown={},
        )
    assert result_score <= max_expected
