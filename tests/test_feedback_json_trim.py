from datetime import datetime, timezone, timedelta

from infrastructure.feedback_trimmer import _trim_votes


def _make_vote(offset_days: int) -> dict[str, object]:
    ts: str = (
        datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=offset_days)
    ).isoformat()
    return {"job_id": f"job-{offset_days}", "voted_at": ts, "vote": "+1", "reasons": ["java"]}


def test_trim_keeps_last_50() -> None:
    """Given 60 records, trim returns the 50 most recent."""
    votes: list[dict[str, object]] = [_make_vote(i) for i in range(60)]
    result: list[dict[str, object]] = _trim_votes(votes)
    assert len(result) == 50
    # The 50 most recent are days 10-59
    kept_ids: set[str] = {str(v["job_id"]) for v in result}
    assert "job-59" in kept_ids
    assert "job-0" not in kept_ids


def test_trim_no_op_when_under_50() -> None:
    """Given 30 records, trim returns all 30 unchanged."""
    votes: list[dict[str, object]] = [_make_vote(i) for i in range(30)]
    result: list[dict[str, object]] = _trim_votes(votes)
    assert len(result) == 30


def test_trim_sorts_by_voted_at() -> None:
    """Trim sorts by voted_at before slicing — out-of-order input is handled correctly."""
    # Build records in reverse order
    votes: list[dict[str, object]] = [_make_vote(i) for i in range(59, -1, -1)]
    result: list[dict[str, object]] = _trim_votes(votes)
    assert len(result) == 50
    kept_ids: set[str] = {str(v["job_id"]) for v in result}
    assert "job-59" in kept_ids
    assert "job-0" not in kept_ids
