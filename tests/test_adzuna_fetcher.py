import json
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

from infrastructure.job_fetchers.adzuna_fetcher import AdzunaFetcher

FIXTURES: Path = Path(__file__).parent / "fixtures"


def _mock_response(data: dict[str, object], status: int = 200) -> MagicMock:
    m: MagicMock = MagicMock()
    m.status_code = status
    m.raise_for_status = MagicMock()
    m.json.return_value = data
    return m


def _load_fixture() -> dict[str, object]:
    return cast(dict[str, object], json.loads((FIXTURES / "adzuna_response.json").read_text()))


def _make_fetcher() -> AdzunaFetcher:
    return AdzunaFetcher(app_id="test_id", app_key="test_key")


def _make_job_item(job_id: str) -> dict[str, object]:
    return {
        "id": job_id,
        "title": "Java Developer",
        "company": {"display_name": "Corp"},
        "location": {"display_name": "Jacksonville, FL"},
        "description": "Job description.",
        "salary_min": None,
        "salary_max": None,
        "redirect_url": f"https://example.com/job/{job_id}",
        "contract_type": None,
        "contract_time": None,
    }


def test_happy_path() -> None:
    data: dict[str, object] = _load_fixture()
    with patch("requests.get", return_value=_mock_response(data)):
        jobs = _make_fetcher().fetch()

    assert len(jobs) == 2

    j = jobs[0]
    assert j.id == "1234567890"
    assert j.title == "Senior Java Developer"
    assert j.company == "Acme Corp"
    assert j.location == "Jacksonville, FL"
    assert j.salary == "$90,000 - $120,000"
    assert j.employment_type == "full-time"
    assert j.remote is None
    assert j.url == "https://api.adzuna.com/v1/api/jobs/us/details/1234567890"
    assert j.required_skills == []


def test_remote_detection() -> None:
    data: dict[str, object] = {
        "results": [
            {
                "id": "111",
                "title": "Remote Java Dev",
                "company": {"display_name": "Corp"},
                "location": {"display_name": "Remote, US"},
                "description": "desc",
                "salary_min": None,
                "salary_max": None,
                "redirect_url": "https://example.com",
                "contract_type": None,
                "contract_time": None,
            }
        ]
    }
    with patch("requests.get", return_value=_mock_response(data)):
        jobs = _make_fetcher().fetch()

    assert jobs[0].remote is True


def test_salary_only_min() -> None:
    item: dict[str, object] = _make_job_item("1")
    item["salary_min"] = 80000
    item["salary_max"] = None
    data: dict[str, object] = {"results": [item]}

    with patch("requests.get", return_value=_mock_response(data)):
        jobs = _make_fetcher().fetch()

    assert jobs[0].salary == "$80,000"


def test_salary_only_max() -> None:
    item: dict[str, object] = _make_job_item("1")
    item["salary_min"] = None
    item["salary_max"] = 100000
    data: dict[str, object] = {"results": [item]}

    with patch("requests.get", return_value=_mock_response(data)):
        jobs = _make_fetcher().fetch()

    assert jobs[0].salary == "$100,000"


def test_salary_none_when_absent() -> None:
    item: dict[str, object] = _make_job_item("1")
    item["salary_min"] = None
    item["salary_max"] = None
    data: dict[str, object] = {"results": [item]}

    with patch("requests.get", return_value=_mock_response(data)):
        jobs = _make_fetcher().fetch()

    assert jobs[0].salary is None


def test_pagination() -> None:
    page1: dict[str, object] = {"results": [_make_job_item(str(i)) for i in range(50)]}
    page2: dict[str, object] = {"results": [_make_job_item(str(i)) for i in range(50, 52)]}

    with patch(
        "requests.get",
        side_effect=[_mock_response(page1), _mock_response(page2)],
    ):
        jobs = _make_fetcher().fetch()

    assert len(jobs) == 52


def test_salary_equal_min_max_shows_single_value() -> None:
    item: dict[str, object] = _make_job_item("1")
    item["salary_min"] = 90000
    item["salary_max"] = 90000
    data: dict[str, object] = {"results": [item]}

    with patch("requests.get", return_value=_mock_response(data)):
        jobs = _make_fetcher().fetch()

    assert jobs[0].salary == "$90,000"


def test_single_page_stop() -> None:
    data: dict[str, object] = _load_fixture()  # 2 results < 50

    with patch("requests.get", return_value=_mock_response(data)) as mock_get:
        _make_fetcher().fetch()

    assert mock_get.call_count == 1
