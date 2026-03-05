import json
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

from infrastructure.job_fetchers.greenhouse_fetcher import GreenhouseFetcher

FIXTURES: Path = Path(__file__).parent / "fixtures"


def _mock_response(data: dict[str, object], status: int = 200) -> MagicMock:
    m: MagicMock = MagicMock()
    m.status_code = status
    m.raise_for_status = MagicMock()
    m.json.return_value = data
    return m


def _load_fixture() -> dict[str, object]:
    return cast(dict[str, object], json.loads((FIXTURES / "greenhouse_response.json").read_text()))


def test_happy_path() -> None:
    data: dict[str, object] = _load_fixture()
    with patch("requests.get", return_value=_mock_response(data)):
        fetcher: GreenhouseFetcher = GreenhouseFetcher(company="sofi", company_name="SoFi")
        jobs = fetcher.fetch()

    assert len(jobs) == 2

    j = jobs[0]
    assert j.id == "7619826003"
    assert j.title == "Analyst Operations Strategy"
    assert j.company == "SoFi"
    assert j.location == "TX - Frisco"
    assert j.salary is None
    assert j.remote is None
    assert j.url == "https://sofi.com/careers/job/7619826003?gh_jid=7619826003"
    # HTML tags stripped from content
    assert "<" not in j.description
    assert "operational strategies" in j.description


def test_remote_detection() -> None:
    data: dict[str, object] = {
        "jobs": [
            {
                "id": 999,
                "title": "Remote Engineer",
                "location": {"name": "Remote - US"},
                "absolute_url": "https://example.com/job",
                "content": "<p>Job description</p>",
            }
        ]
    }
    with patch("requests.get", return_value=_mock_response(data)):
        fetcher: GreenhouseFetcher = GreenhouseFetcher(company="test", company_name="Test Co")
        jobs = fetcher.fetch()

    assert jobs[0].remote is True
    assert jobs[0].location == "Remote - US"


def test_missing_location() -> None:
    data: dict[str, object] = {
        "jobs": [
            {
                "id": 123,
                "title": "Engineer",
                "location": None,
                "absolute_url": "https://example.com/job",
                "content": "",
            }
        ]
    }
    with patch("requests.get", return_value=_mock_response(data)):
        fetcher: GreenhouseFetcher = GreenhouseFetcher(company="test", company_name="Test Co")
        jobs = fetcher.fetch()

    assert jobs[0].location == ""
    assert jobs[0].remote is None
