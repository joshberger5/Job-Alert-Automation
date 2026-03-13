"""Tests for _fetch_jobs 3-tuple return and timeout handling."""
from unittest.mock import MagicMock, patch

from main import _fetch_jobs
from application.fetcher_result import FetcherFailure
from domain.job import Job


def test_fetch_jobs_returns_tuple() -> None:
    """_fetch_jobs returns a 3-tuple (jobs, failures, warnings)."""
    all_jobs: list[Job]
    failures: list[FetcherFailure]
    fetch_warnings: list[str]
    all_jobs, failures, fetch_warnings = _fetch_jobs([], timeout=30)
    assert isinstance(all_jobs, list)
    assert isinstance(failures, list)
    assert isinstance(fetch_warnings, list)


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
            all_jobs: list[Job]
            failures: list[FetcherFailure]
            fetch_warnings: list[str]
            all_jobs, failures, fetch_warnings = _fetch_jobs([mock_fetcher], timeout=1)

    assert any(f.get("error") == "TIMEOUT" for f in failures), (
        "Timed-out fetcher must produce FetcherFailure with error='TIMEOUT'"
    )
    assert any(f.get("attempts") == 1 for f in failures), (
        "Timed-out fetcher must have attempts=1 (no retry)"
    )
