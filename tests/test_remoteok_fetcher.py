import json
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

from infrastructure.job_fetchers.remoteok_fetcher import RemoteOKFetcher

FIXTURES: Path = Path(__file__).parent / "fixtures"


def _mock_response(data: list[object], status: int = 200) -> MagicMock:
    m: MagicMock = MagicMock()
    m.status_code = status
    m.raise_for_status = MagicMock()
    m.json.return_value = data
    return m


def _load_fixture() -> list[object]:
    return cast(list[object], json.loads((FIXTURES / "remoteok_response.json").read_text()))


def test_happy_path() -> None:
    data: list[object] = _load_fixture()
    with patch("requests.get", return_value=_mock_response(data)):
        fetcher: RemoteOKFetcher = RemoteOKFetcher(tags="java")
        jobs = fetcher.fetch()

    # metadata element at index 0 is skipped → 2 jobs
    assert len(jobs) == 2

    j = jobs[0]
    assert j.id == "1130565"
    assert j.title == "Early Career Software Engineer"
    assert j.company == "Anduril Industries"
    assert j.location == "Bellevue"
    assert j.required_skills == ["java", "python", "docker"]
    assert j.remote is True
    # HTML tags stripped from description
    assert "<" not in j.description
    assert "Java" in j.description


def test_null_location() -> None:
    data: list[object] = [
        {"last_updated": 0, "legal": ""},
        {
            "id": "999",
            "company": "Corp",
            "position": "Engineer",
            "tags": [],
            "description": "desc",
            "location": None,
            "url": "https://remoteok.com/job/999",
        },
    ]
    with patch("requests.get", return_value=_mock_response(data)):
        jobs = RemoteOKFetcher().fetch()

    assert jobs[0].location == "Worldwide"


def test_null_tags() -> None:
    data: list[object] = [
        {"last_updated": 0, "legal": ""},
        {
            "id": "999",
            "company": "Corp",
            "position": "Engineer",
            "tags": None,
            "description": "desc",
            "location": "Anywhere",
            "url": "https://remoteok.com/job/999",
        },
    ]
    with patch("requests.get", return_value=_mock_response(data)):
        jobs = RemoteOKFetcher().fetch()

    assert jobs[0].required_skills == []
