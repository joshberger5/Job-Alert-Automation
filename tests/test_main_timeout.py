"""Tests for _fetch_jobs 3-tuple return and timeout handling (red until Plan 02-02)."""
from unittest.mock import MagicMock, patch

from main import _fetch_jobs
from application.fetcher_result import FetcherFailure
from domain.job import Job


def test_fetch_jobs_returns_tuple() -> None:
    """_fetch_jobs returns a 3-tuple (jobs, failures, warnings) after Plan 02."""
    result: object = _fetch_jobs([], timeout=30)
    assert isinstance(result, tuple), "_fetch_jobs must return a 3-tuple"
    assert len(result) == 3  # type: ignore[arg-type]


def test_fetch_jobs_timeout_marked_failed() -> None:
    """A fetcher that times out produces FetcherFailure(error='TIMEOUT', attempts=1)."""
    mock_fetcher: MagicMock = MagicMock()
    mock_fetcher.company_name = "SlowCo"

    with patch("main.ThreadPoolExecutor") as mock_pool_cls:
        mock_pool: MagicMock = MagicMock()
        mock_pool_cls.return_value.__enter__.return_value = mock_pool

        mock_future: MagicMock = MagicMock()
        mock_future.result.side_effect = TimeoutError("wall clock exceeded")
        mock_pool.submit.return_value = mock_future

        with patch("main.as_completed", return_value=[mock_future]):
            result: object = _fetch_jobs([mock_fetcher], timeout=1)

    assert isinstance(result, tuple), "_fetch_jobs must return a 3-tuple"
    all_jobs: list[Job]
    failures: list[FetcherFailure]
    warnings: list[str]
    all_jobs, failures, warnings = result  # type: ignore[misc]
    assert any(f.get("error") == "TIMEOUT" for f in failures), (
        "Timed-out fetcher must produce FetcherFailure with error='TIMEOUT'"
    )
    assert any(f.get("attempts") == 1 for f in failures), (
        "Timed-out fetcher must have attempts=1 (no retry)"
    )
