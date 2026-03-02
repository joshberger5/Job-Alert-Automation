import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from infrastructure.job_fetchers.workday_fetcher import WorkdayFetcher

FIXTURES: Path = Path(__file__).parent / "fixtures"

_BASE_URL: str = "https://example.wd1.myworkdayjobs.com"
_RECRUITING_BASE: str = "https://example.wd1.myworkdayjobs.com/en-US/Jobs"


def _mock_post(data: dict[str, object], status: int = 200) -> MagicMock:
    m: MagicMock = MagicMock()
    m.status_code = status
    m.raise_for_status = MagicMock()
    m.json.return_value = data
    return m


def _mock_html(html: str, status: int = 200) -> MagicMock:
    m: MagicMock = MagicMock()
    m.status_code = status
    m.raise_for_status = MagicMock()
    m.text = html
    return m


def _load_fixture() -> dict[str, object]:
    return json.loads((FIXTURES / "workday_response.json").read_text())


def _make_fetcher(fetch_descriptions: bool = False) -> WorkdayFetcher:
    return WorkdayFetcher(
        base_url=_BASE_URL,
        tenant="example",
        company="ExampleJobs",
        company_name="Example Co",
        recruiting_base=_RECRUITING_BASE,
        fetch_descriptions=fetch_descriptions,
    )


def _make_posting(i: int) -> dict[str, object]:
    return {
        "title": f"Job {i}",
        "externalPath": f"/job/Location/Job_{i}",
        "locationsText": "Jacksonville, FL",
        "postedOn": "Posted 30+ Days Ago",
        "bulletFields": [f"R{i:03d}"],
    }


def test_happy_path_no_descriptions() -> None:
    data: dict[str, object] = _load_fixture()
    with patch("requests.post", return_value=_mock_post(data)):
        jobs = _make_fetcher(fetch_descriptions=False).fetch()

    assert len(jobs) == 2

    j = jobs[0]
    assert j.id == "R001"
    assert j.title == "Software Engineer I"
    assert j.company == "Example Co"
    assert j.location == "Jacksonville, FL"
    assert j.remote is None
    assert j.description == ""
    assert j.url == f"{_RECRUITING_BASE}/job/Jacksonville-FL/Software-Engineer_R001"


def test_pagination() -> None:
    page1: dict[str, object] = {
        "total": 25,
        "jobPostings": [_make_posting(i) for i in range(20)],
    }
    page2: dict[str, object] = {
        "total": 25,
        "jobPostings": [_make_posting(i) for i in range(20, 25)],
    }

    with patch(
        "requests.post",
        side_effect=[_mock_post(page1), _mock_post(page2)],
    ):
        jobs = _make_fetcher().fetch()

    assert len(jobs) == 25


def test_remote_detection() -> None:
    data: dict[str, object] = {
        "total": 1,
        "jobPostings": [
            {
                "title": "Remote Java Developer",
                "externalPath": "/job/Remote/Java-Developer_R999",
                "locationsText": "Remote, United States",
                "bulletFields": ["R999"],
            }
        ],
    }

    with patch("requests.post", return_value=_mock_post(data)):
        jobs = _make_fetcher().fetch()

    assert jobs[0].remote is True


def test_fetch_descriptions() -> None:
    fixture_data: dict[str, object] = _load_fixture()
    detail_html: str = (FIXTURES / "workday_detail.html").read_text()

    def _get_side_effect(url: str, **kwargs: object) -> MagicMock:
        return _mock_html(detail_html)

    with patch("requests.post", return_value=_mock_post(fixture_data)), patch(
        "requests.get", side_effect=_get_side_effect
    ):
        jobs = _make_fetcher(fetch_descriptions=True).fetch()

    assert len(jobs) == 2
    # HTML tags stripped from ld+json description field
    assert "Software engineer role" in jobs[0].description
    assert "<" not in jobs[0].description
