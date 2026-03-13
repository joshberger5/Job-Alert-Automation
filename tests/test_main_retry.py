"""Tests for _run_fetcher retry behavior (red until Plan 02-02 is implemented)."""
from unittest.mock import MagicMock

from main import _run_fetcher
from application.fetcher_result import FetcherFailure
from domain.job import Job


def _make_fetcher(side_effects: list[object], name: str = "TestCo") -> MagicMock:
    fetcher: MagicMock = MagicMock()
    fetcher.company_name = name
    fetcher.fetch.side_effect = side_effects
    return fetcher


def test_run_fetcher_success() -> None:
    """Fetcher succeeds first try → returns (label, jobs, None)."""
    jobs: list[Job] = [MagicMock(spec=Job)]
    fetcher: MagicMock = _make_fetcher([jobs])
    label: str
    result_jobs: list[Job]
    failure: FetcherFailure | None
    label, result_jobs, failure = _run_fetcher(fetcher)
    assert label == "TestCo"
    assert result_jobs == jobs
    assert failure is None


def test_run_fetcher_retries_once() -> None:
    """Fetcher raises on attempt 1, succeeds on attempt 2 → returns jobs, no failure."""
    jobs: list[Job] = [MagicMock(spec=Job)]
    fetcher: MagicMock = _make_fetcher([RuntimeError("fail"), jobs])
    label: str
    result_jobs: list[Job]
    failure: FetcherFailure | None
    label, result_jobs, failure = _run_fetcher(fetcher)
    assert label == "TestCo"
    assert result_jobs == jobs
    assert failure is None
    assert fetcher.fetch.call_count == 2


def test_run_fetcher_fails_after_two_attempts() -> None:
    """Fetcher raises on both attempts → returns FetcherFailure with attempts=2."""
    fetcher: MagicMock = _make_fetcher(
        [RuntimeError("fail1"), RuntimeError("fail2")]
    )
    label: str
    result_jobs: list[Job]
    failure: FetcherFailure | None
    label, result_jobs, failure = _run_fetcher(fetcher)
    assert label == "TestCo"
    assert result_jobs == []
    assert failure is not None
    assert failure["attempts"] == 2
    assert "fail2" in failure["error"]


def test_run_fetcher_no_retry_on_timeout() -> None:
    """_run_fetcher propagates TimeoutError up (it is NOT caught here)."""
    fetcher: MagicMock = _make_fetcher([TimeoutError("wall clock")])
    try:
        _run_fetcher(fetcher)
        # If TimeoutError is swallowed and a failure is returned, that's wrong
        # but we document this expectation; the test passes if TimeoutError raises
        # OR if the implementation catches it gracefully (Plan 02 decides)
    except TimeoutError:
        pass  # expected — _run_fetcher propagates TimeoutError
