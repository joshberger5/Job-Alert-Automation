"""Tests for infrastructure.fetcher_registry — verifies critical fetcher configuration."""
import os
from unittest.mock import patch

from infrastructure.fetcher_registry import build_fetchers
from infrastructure.job_fetchers.workday_fetcher import WorkdayFetcher


def _build() -> list[WorkdayFetcher]:
    """Build all fetchers with dummy env vars and return just the Workday ones."""
    env: dict[str, str] = {
        "ADZUNA_APP_ID": "dummy_id",
        "ADZUNA_APP_KEY": "dummy_key",
    }
    with patch.dict(os.environ, env):
        fetchers, _ = build_fetchers()
    return [f for f in fetchers if isinstance(f, WorkdayFetcher)]


def test_fis_fetcher_has_fetch_descriptions_enabled() -> None:
    """FIS descriptions were silently empty because fetch_descriptions defaulted to False."""
    workday_fetchers: list[WorkdayFetcher] = _build()
    fis_fetchers: list[WorkdayFetcher] = [
        f for f in workday_fetchers if f.company_name == "FIS Global"
    ]
    assert len(fis_fetchers) == 1, "Expected exactly one FIS Global WorkdayFetcher"
    assert fis_fetchers[0].fetch_descriptions is True, (
        "FIS fetcher must have fetch_descriptions=True — "
        "without it all FIS job descriptions are empty and score 0"
    )
