import json
import pytest
from pathlib import Path
from unittest.mock import patch

from application.feedback_bias_service import FeedbackBiasService, FEEDBACK_WEIGHT, _FEEDBACK_PATH


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_feedback(tmp_path: Path, entries: list[dict[str, object]]) -> Path:
    p: Path = tmp_path / "feedback.json"
    p.write_text(json.dumps(entries), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# SCORE-04: Multiplier behavior tests
# ---------------------------------------------------------------------------


def test_multiplier_is_one_when_no_feedback_file() -> None:
    """When feedback.json does not exist, apply() returns base score and multiplier 1.0."""
    with patch("application.feedback_bias_service._FEEDBACK_PATH", Path("/nonexistent/feedback.json")):
        svc: FeedbackBiasService = FeedbackBiasService()
        final_score, _, multiplier = svc.apply(10, "java developer", {})

    assert final_score == 10
    assert multiplier == 1.0


def test_token_below_threshold_does_not_apply(tmp_path: Path) -> None:
    """Tokens with |net_votes| < 3 do not affect the multiplier."""
    # 2 upvotes for "java" — net = 2, below threshold of 3
    entries: list[dict[str, object]] = [
        {"job_id": "a", "reasons": ["java"], "vote": "+1"},
        {"job_id": "b", "reasons": ["java"], "vote": "+1"},
    ]
    feedback_path: Path = _write_feedback(tmp_path, entries)

    with patch("application.feedback_bias_service._FEEDBACK_PATH", feedback_path):
        svc: FeedbackBiasService = FeedbackBiasService()
        final_score, _, multiplier = svc.apply(10, "java developer", {})

    assert multiplier == 1.0
    assert final_score == 10


def test_token_at_threshold_boosts_score(tmp_path: Path) -> None:
    """Token with net_votes == 3 contributes; score for matching job content increases."""
    entries: list[dict[str, object]] = [
        {"job_id": "a", "reasons": ["java"], "vote": "+1"},
        {"job_id": "b", "reasons": ["java"], "vote": "+1"},
        {"job_id": "c", "reasons": ["java"], "vote": "+1"},
    ]
    feedback_path: Path = _write_feedback(tmp_path, entries)

    with patch("application.feedback_bias_service._FEEDBACK_PATH", feedback_path):
        svc: FeedbackBiasService = FeedbackBiasService()
        final_score, _, multiplier = svc.apply(10, "java developer", {})

    assert final_score > 10
    assert multiplier > 1.0


def test_multiplier_clamped_at_minimum(tmp_path: Path) -> None:
    """Strong negative votes clamp multiplier to 0.5; final_score >= round(base * 0.5)."""
    # 10 downvotes each for several tokens found in job content → multiplier goes very negative
    tokens: list[str] = ["java", "python", "sql", "react", "linux"]
    entries: list[dict[str, object]] = [
        {"job_id": f"job-{t}-{i}", "reasons": [t], "vote": "-1"}
        for t in tokens
        for i in range(10)
    ]
    feedback_path: Path = _write_feedback(tmp_path, entries)
    job_content: str = "java python sql react linux developer"

    with patch("application.feedback_bias_service._FEEDBACK_PATH", feedback_path):
        svc: FeedbackBiasService = FeedbackBiasService()
        final_score, _, multiplier = svc.apply(10, job_content, {})

    assert multiplier == 0.5
    assert final_score >= round(10 * 0.5)


def test_multiplier_clamped_at_maximum(tmp_path: Path) -> None:
    """Strong positive votes clamp multiplier to 2.0; final_score <= round(base * 2.0)."""
    tokens: list[str] = ["java", "python", "sql", "react", "linux"]
    entries: list[dict[str, object]] = [
        {"job_id": f"job-{t}-{i}", "reasons": [t], "vote": "+1"}
        for t in tokens
        for i in range(10)
    ]
    feedback_path: Path = _write_feedback(tmp_path, entries)
    job_content: str = "java python sql react linux developer"

    with patch("application.feedback_bias_service._FEEDBACK_PATH", feedback_path):
        svc: FeedbackBiasService = FeedbackBiasService()
        final_score, _, multiplier = svc.apply(10, job_content, {})

    assert multiplier == 2.0
    assert final_score <= round(10 * 2.0)


def test_feedback_score_delta_in_breakdown(tmp_path: Path) -> None:
    """Returned breakdown includes 'feedback_score_delta' when multiplier is applied."""
    entries: list[dict[str, object]] = [
        {"job_id": f"job-{i}", "reasons": ["java"], "vote": "+1"}
        for i in range(3)
    ]
    feedback_path: Path = _write_feedback(tmp_path, entries)

    with patch("application.feedback_bias_service._FEEDBACK_PATH", feedback_path):
        svc: FeedbackBiasService = FeedbackBiasService()
        final_score, breakdown, _ = svc.apply(10, "java developer", {"core:java": 10})

    assert "feedback_score_delta" in breakdown
    assert isinstance(breakdown["feedback_score_delta"], int)
    assert breakdown["feedback_score_delta"] == final_score - 10


def test_no_match_in_content_multiplier_stays_one(tmp_path: Path) -> None:
    """Even with threshold-passing tokens, no match in job_content → multiplier stays 1.0."""
    entries: list[dict[str, object]] = [
        {"job_id": f"job-{i}", "reasons": ["java"], "vote": "+1"}
        for i in range(3)
    ]
    feedback_path: Path = _write_feedback(tmp_path, entries)

    with patch("application.feedback_bias_service._FEEDBACK_PATH", feedback_path):
        svc: FeedbackBiasService = FeedbackBiasService()
        final_score, _, multiplier = svc.apply(10, "python developer with c++ skills", {})

    assert multiplier == 1.0
    assert final_score == 10


def test_parse_error_in_feedback_json_treated_as_empty(tmp_path: Path) -> None:
    """A malformed feedback.json is treated as missing — bias_map empty, multiplier 1.0."""
    bad_path: Path = tmp_path / "feedback.json"
    bad_path.write_text("not valid json", encoding="utf-8")

    with patch("application.feedback_bias_service._FEEDBACK_PATH", bad_path):
        svc: FeedbackBiasService = FeedbackBiasService()
        final_score, _, multiplier = svc.apply(10, "java developer", {})

    assert multiplier == 1.0
    assert final_score == 10


def test_negative_vote_normalization(tmp_path: Path) -> None:
    """Vote values '-1' (string), -1 (int) all normalize correctly."""
    entries: list[dict[str, object]] = [
        {"job_id": "a", "reasons": ["java"], "vote": "-1"},
        {"job_id": "b", "reasons": ["java"], "vote": "-1"},
        {"job_id": "c", "reasons": ["java"], "vote": "-1"},
    ]
    feedback_path: Path = _write_feedback(tmp_path, entries)

    with patch("application.feedback_bias_service._FEEDBACK_PATH", feedback_path):
        svc: FeedbackBiasService = FeedbackBiasService()
        final_score, _, multiplier = svc.apply(10, "java developer", {})

    # net = -3, multiplier = 1.0 + (-3 * 0.5) = -0.5, clamped to 0.5
    assert multiplier == 0.5
    assert final_score == round(10 * 0.5)


def test_multi_reason_accumulates_independently(tmp_path: Path) -> None:
    """Multiple reasons in one record each contribute as independent tokens."""
    entries: list[dict[str, object]] = [
        {"job_id": f"job-{i}", "reasons": ["java", "spring boot"], "vote": "+1"}
        for i in range(3)
    ]
    feedback_path: Path = _write_feedback(tmp_path, entries)

    with patch("application.feedback_bias_service._FEEDBACK_PATH", feedback_path):
        svc: FeedbackBiasService = FeedbackBiasService()
        _, _, multi_multiplier = svc.apply(10, "java spring boot developer", {})
        _, _, java_only_multiplier = svc.apply(10, "java developer", {})
        _, _, no_match_multiplier = svc.apply(10, "python developer", {})

    # Both tokens threshold-met → matching both gives larger multiplier than matching one
    assert multi_multiplier > java_only_multiplier
    assert java_only_multiplier > 1.0
    assert no_match_multiplier == 1.0
