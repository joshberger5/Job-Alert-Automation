import json
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

from infrastructure.job_fetchers.lever_fetcher import LeverFetcher

FIXTURES: Path = Path(__file__).parent / "fixtures"


def _mock_response(data: list[dict[str, object]], status: int = 200) -> MagicMock:
    m: MagicMock = MagicMock()
    m.status_code = status
    m.raise_for_status = MagicMock()
    m.json.return_value = data
    return m


def _load_fixture() -> list[dict[str, object]]:
    return cast(list[dict[str, object]], json.loads((FIXTURES / "lever_response.json").read_text()))


def _make_item(
    commitment: str = "Full-time",
    location: str = "",
    salary_range: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "id": "abc-123",
        "text": "Software Engineer",
        "categories": {"commitment": commitment, "location": location},
        "salaryRange": salary_range,
        "descriptionPlain": "Job description text.",
        "hostedUrl": "https://jobs.lever.co/test/abc-123",
    }


def test_happy_path() -> None:
    data: list[dict[str, object]] = _load_fixture()
    with patch("requests.get", return_value=_mock_response(data)):
        fetcher: LeverFetcher = LeverFetcher(company="dnb", company_name="D&B")
        jobs = fetcher.fetch()

    assert len(jobs) == 2

    j = jobs[0]
    assert j.id == "6590549e-d893-4e0e-8934-dda77ef05223"
    assert j.title == "Account Executive II, SLED (R-18831)"
    assert j.company == "D&B"
    assert j.salary == "$123,100 - $206,800"
    assert j.employment_type == "full-time"
    assert j.remote is True  # "remote" in "Remote - United States"
    assert j.url == "https://jobs.lever.co/dnb/6590549e-d893-4e0e-8934-dda77ef05223"


def test_location_filter_query_param() -> None:
    with patch("requests.get", return_value=_mock_response([])) as mock_get:
        LeverFetcher(company="test", company_name="Test", location="New York").fetch()

    params: dict[str, str] = mock_get.call_args.kwargs["params"]
    assert params.get("location") == "New York"
    assert params.get("mode") == "json"


def test_no_salary() -> None:
    data: list[dict[str, object]] = [_make_item(salary_range=None)]
    with patch("requests.get", return_value=_mock_response(data)):
        jobs = LeverFetcher(company="test", company_name="Test").fetch()

    assert jobs[0].salary is None


def test_employment_type_variants() -> None:
    cases: list[tuple[str, str]] = [
        ("Contract", "contract"),
        ("Part-time", "part-time"),
        ("Internship", "internship"),
    ]
    for commitment, expected in cases:
        data: list[dict[str, object]] = [_make_item(commitment=commitment)]
        with patch("requests.get", return_value=_mock_response(data)):
            jobs = LeverFetcher(company="test", company_name="Test").fetch()
        assert jobs[0].employment_type == expected, (
            f"commitment={commitment!r} → expected {expected!r}, got {jobs[0].employment_type!r}"
        )
