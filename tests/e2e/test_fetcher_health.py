"""E2E fetcher health checks — makes real HTTP calls to each fetcher endpoint.

Run with:
    py -m pytest tests/e2e/ -v

Skipped automatically when ADZUNA_APP_ID / ADZUNA_APP_KEY are absent.
"""

import pytest
from dotenv import load_dotenv

from domain.job import Job
from infrastructure.job_fetchers import JobFetcher
from infrastructure.fetcher_registry import build_fetchers

load_dotenv()


def _get_fetchers() -> list[JobFetcher]:
    try:
        fetchers, _ = build_fetchers()
        return fetchers
    except KeyError:
        return []


_FETCHERS: list[JobFetcher] = _get_fetchers()
_IDS: list[str] = [
    f"{fetcher.company_name}_{i}" for i, fetcher in enumerate(_FETCHERS)
]


@pytest.mark.e2e
@pytest.mark.parametrize("fetcher", _FETCHERS, ids=_IDS)
def test_fetcher_health(fetcher: JobFetcher) -> None:
    jobs: list[Job] = fetcher.fetch()
    assert isinstance(jobs, list)
    print(f"\n  → {len(jobs)} jobs returned")
