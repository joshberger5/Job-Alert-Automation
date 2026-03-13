"""Tests for JSearchFetcher (red until Plan 02-03 is implemented)."""
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from infrastructure.job_fetchers.jsearch_fetcher import JSearchFetcher
from domain.job import Job


_FIXTURE_PATH: Path = Path(__file__).parent / "fixtures" / "jsearch_response.json"


def _load_fixture() -> dict[str, object]:
    with open(_FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)  # type: ignore[return-value]


def _mock_response(data: dict[str, object]) -> MagicMock:
    resp: MagicMock = MagicMock()
    resp.json.return_value = data
    resp.raise_for_status.return_value = None
    return resp


def test_jsearch_happy_path() -> None:
    """Mock requests.get to return fixture → returns list[Job] with correct count."""
    fixture: dict[str, object] = _load_fixture()
    with patch("requests.get", return_value=_mock_response(fixture)):
        fetcher: JSearchFetcher = JSearchFetcher(api_key="test-key", query="java developer")
        jobs: list[Job] = fetcher.fetch()
    assert len(jobs) == 1
    assert jobs[0].id == "jsearch-001"
    assert jobs[0].title == "Java Developer"
    assert jobs[0].company == "Test Corp"


def test_jsearch_empty_key_raises() -> None:
    """JSearchFetcher('') raises ValueError."""
    with pytest.raises(ValueError):
        JSearchFetcher(api_key="", query="java developer")


def test_jsearch_field_mapping() -> None:
    """Verify field mapping: job_id→id, job_title→title, employer_name→company,
    job_city+job_state→location, job_is_remote→remote."""
    fixture: dict[str, object] = _load_fixture()
    with patch("requests.get", return_value=_mock_response(fixture)):
        fetcher: JSearchFetcher = JSearchFetcher(api_key="test-key", query="java developer")
        jobs: list[Job] = fetcher.fetch()
    assert len(jobs) == 1
    job: Job = jobs[0]
    assert job.id == "jsearch-001"
    assert job.title == "Java Developer"
    assert job.company == "Test Corp"
    assert "Jacksonville" in job.location
    assert "FL" in job.location
    # job_is_remote=false → remote is not True
    assert job.remote is not True
