import json
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

from infrastructure.job_fetchers.boa_fetcher import BankOfAmericaFetcher

FIXTURES: Path = Path(__file__).parent / "fixtures"

_BOA_BASE: str = "https://careers.bankofamerica.com"


def _mock_response(data: dict[str, object], status: int = 200) -> MagicMock:
    m: MagicMock = MagicMock()
    m.status_code = status
    m.raise_for_status = MagicMock()
    m.json.return_value = data
    return m


def _load_fixture() -> dict[str, object]:
    return cast(dict[str, object], json.loads((FIXTURES / "boa_response.json").read_text()))


def _make_listing(i: int) -> dict[str, object]:
    return {
        "postingTitle": f"Job {i}",
        "jcrURL": f"/en-us/details/{i}/job",
        "family": "Technology",
        "lob": "Global Tech",
        "location": "Jacksonville, FL",
    }


def test_happy_path() -> None:
    data: dict[str, object] = _load_fixture()
    with patch("requests.get", return_value=_mock_response(data)):
        fetcher: BankOfAmericaFetcher = BankOfAmericaFetcher()
        jobs = fetcher.fetch()

    assert len(jobs) == 2

    j = jobs[0]
    assert j.title == "Software Engineer II"
    assert j.id == "/en-us/details/24102906/software-engineer-ii"
    assert j.company == "Bank of America"
    assert j.location == "Jacksonville, FL"
    assert j.url == f"{_BOA_BASE}/en-us/details/24102906/software-engineer-ii"
    assert j.description == "Technology | Global Technology & Operations"
    assert j.remote is None
    assert j.salary is None


def test_pagination() -> None:
    page1: dict[str, object] = {
        "jobsList": [_make_listing(i) for i in range(50)],
        "totalJobsCount": 53,
    }
    page2: dict[str, object] = {
        "jobsList": [_make_listing(i) for i in range(50, 53)],
        "totalJobsCount": 53,
    }

    with patch(
        "requests.get",
        side_effect=[_mock_response(page1), _mock_response(page2)],
    ):
        jobs = BankOfAmericaFetcher().fetch()

    assert len(jobs) == 53


def test_missing_jcr_url() -> None:
    data: dict[str, object] = {
        "jobsList": [
            {
                "postingTitle": "Software Engineer",
                "jcrURL": "",
                "family": "Technology",
                "lob": "Global Tech",
                "location": "Jacksonville, FL",
            }
        ]
    }

    with patch("requests.get", return_value=_mock_response(data)):
        jobs = BankOfAmericaFetcher().fetch()

    assert jobs[0].url is None
    assert jobs[0].id == ""
