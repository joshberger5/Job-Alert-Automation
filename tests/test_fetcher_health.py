"""Tests for infrastructure.fetcher_health — consecutive failure tracking."""
from datetime import datetime

from application.fetcher_result import FetcherFailure
from infrastructure.fetcher_health import FetcherHealth, update_health

_NOW: datetime = datetime(2026, 3, 21, 10, 0, 0)


def _failure(company: str, error: str = "SSL error", attempts: int = 2) -> FetcherFailure:
    return {"company": company, "error": error, "attempts": attempts}


class TestNewFetcher:
    def test_first_failure_starts_at_one(self) -> None:
        """A fetcher not in the health data that fails starts at consecutive_failures=1."""
        result: FetcherHealth = update_health(
            current={},
            failures=[_failure("Acme")],
            all_labels=["Acme"],
            now=_NOW,
        )
        assert result["Acme"]["consecutive_failures"] == 1

    def test_first_failure_records_error(self) -> None:
        """last_error is set to the failure's error string."""
        result: FetcherHealth = update_health(
            current={},
            failures=[_failure("Acme", error="connection refused")],
            all_labels=["Acme"],
            now=_NOW,
        )
        assert result["Acme"]["last_error"] == "connection refused"

    def test_first_failure_records_timestamp(self) -> None:
        """last_failed_at is set to the now timestamp."""
        result: FetcherHealth = update_health(
            current={},
            failures=[_failure("Acme")],
            all_labels=["Acme"],
            now=_NOW,
        )
        assert result["Acme"]["last_failed_at"] == "2026-03-21T10:00:00"

    def test_successful_new_fetcher_not_added(self) -> None:
        """A fetcher not in history that succeeds is not added to health data."""
        result: FetcherHealth = update_health(
            current={},
            failures=[],
            all_labels=["Acme"],
            now=_NOW,
        )
        assert "Acme" not in result


class TestExistingFetcher:
    def test_increments_on_consecutive_failure(self) -> None:
        """An already-failing fetcher gets its count incremented."""
        current: FetcherHealth = {
            "Acme": {
                "consecutive_failures": 2,
                "last_error": "old error",
                "last_failed_at": "2026-03-20T00:00:00",
            }
        }
        result: FetcherHealth = update_health(
            current=current,
            failures=[_failure("Acme", error="new error")],
            all_labels=["Acme"],
            now=_NOW,
        )
        assert result["Acme"]["consecutive_failures"] == 3

    def test_resets_to_zero_on_success(self) -> None:
        """A previously failing fetcher that now succeeds resets to 0."""
        current: FetcherHealth = {
            "Acme": {
                "consecutive_failures": 3,
                "last_error": "SSL",
                "last_failed_at": "2026-03-20T00:00:00",
            }
        }
        result: FetcherHealth = update_health(
            current=current,
            failures=[],
            all_labels=["Acme"],
            now=_NOW,
        )
        assert result["Acme"]["consecutive_failures"] == 0

    def test_preserves_last_error_on_reset(self) -> None:
        """last_error is preserved when resetting (useful for the repair agent's history)."""
        current: FetcherHealth = {
            "Acme": {
                "consecutive_failures": 3,
                "last_error": "SSL",
                "last_failed_at": "2026-03-20T00:00:00",
            }
        }
        result: FetcherHealth = update_health(
            current=current,
            failures=[],
            all_labels=["Acme"],
            now=_NOW,
        )
        assert result["Acme"]["last_error"] == "SSL"


class TestIsolation:
    def test_unrelated_fetchers_not_in_all_labels_are_preserved(self) -> None:
        """Fetchers not in all_labels are left unchanged."""
        current: FetcherHealth = {
            "OldCo": {
                "consecutive_failures": 5,
                "last_error": "404",
                "last_failed_at": "2026-03-01T00:00:00",
            }
        }
        result: FetcherHealth = update_health(
            current=current,
            failures=[],
            all_labels=["Acme"],
            now=_NOW,
        )
        assert result["OldCo"]["consecutive_failures"] == 5

    def test_timeout_counts_as_failure(self) -> None:
        """A TIMEOUT error (attempts=1) increments consecutive_failures."""
        timeout: FetcherFailure = {"company": "Acme", "error": "TIMEOUT", "attempts": 1}
        result: FetcherHealth = update_health(
            current={},
            failures=[timeout],
            all_labels=["Acme"],
            now=_NOW,
        )
        assert result["Acme"]["consecutive_failures"] == 1
        assert result["Acme"]["last_error"] == "TIMEOUT"

    def test_multiple_fetchers_updated_independently(self) -> None:
        """Multiple fetchers are updated independently in one call."""
        current: FetcherHealth = {
            "Alpha": {
                "consecutive_failures": 1,
                "last_error": "err",
                "last_failed_at": "2026-03-20T00:00:00",
            }
        }
        result: FetcherHealth = update_health(
            current=current,
            failures=[_failure("Beta")],
            all_labels=["Alpha", "Beta"],
            now=_NOW,
        )
        assert result["Alpha"]["consecutive_failures"] == 0
        assert result["Beta"]["consecutive_failures"] == 1
