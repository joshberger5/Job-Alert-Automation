"""
tests/test_landstar_fetcher.py
================================
All HTTP is mocked — no network calls are made.
"""

from unittest.mock import MagicMock, patch

import pytest

from infrastructure.job_fetchers.landstar_fetcher import LandstarFetcher


# ── fixtures ────────────────────────────────────────────────────────────── #

def _make_posting(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "clientNamespace": "landstar",
        "jobBoardId": 1,
        "jobPostingId": 9999,
        "jobReqId": 1000,
        "jobTitle": "Software Engineer",
        "jobDescription": (
            "Location: Hybrid Jacksonville, FL\n"
            "Salary range: $92,000 - $114,000\n"
            "Build backend services in Java and Spring Boot."
        ),
        "hasVirtualLocation": False,
        "postingStartTimestampUTC": "2026-03-01T06:00:00+00:00",
        "postingExpiryTimestampUTC": None,
        "isEvergreen": False,
        "postingLocations": [
            {
                "formattedAddress": "Landstar System, Inc., 13410 Sutton Park Dr S, Jacksonville, Florida, United States of America",
                "locationId": 1325,
                "locationType": 1,
                "isoCountryCode": "US",
                "stateCode": "FL",
                "cityName": "Jacksonville",
            }
        ],
        "postingAppliedStatus": {"jobPostingId": 9999, "hasApplied": False, "canApplyAgain": True},
        "searchScore": 0,
    }
    base.update(overrides)
    return base


def _mock_response(postings: list[dict[str, object]], max_count: int | None = None) -> MagicMock:
    mock: MagicMock = MagicMock()
    mock.raise_for_status.return_value = None
    mock.json.return_value = {
        "jobPostings": postings,
        "maxCount": max_count if max_count is not None else len(postings),
        "offset": 0,
        "count": len(postings),
    }
    return mock


# ── tests ───────────────────────────────────────────────────────────────── #

class TestLandstarFetcherFieldMapping:
    """Basic field mapping from a standard posting."""

    def test_id_uses_posting_id(self) -> None:
        posting: dict[str, object] = _make_posting(jobPostingId=10405)
        with patch("requests.Session.post", return_value=_mock_response([posting])):
            jobs = LandstarFetcher().fetch()
        assert len(jobs) == 1
        assert jobs[0].id == "landstar_10405"

    def test_title_stripped(self) -> None:
        posting: dict[str, object] = _make_posting(jobTitle="  Sr. System Engineer  ")
        with patch("requests.Session.post", return_value=_mock_response([posting])):
            jobs = LandstarFetcher().fetch()
        assert jobs[0].title == "Sr. System Engineer"

    def test_company_is_landstar(self) -> None:
        with patch("requests.Session.post", return_value=_mock_response([_make_posting()])):
            jobs = LandstarFetcher().fetch()
        assert jobs[0].company == "Landstar System"

    def test_location_from_primary_posting_location(self) -> None:
        posting: dict[str, object] = _make_posting()  # Jacksonville, FL
        with patch("requests.Session.post", return_value=_mock_response([posting])):
            jobs = LandstarFetcher().fetch()
        assert "Jacksonville" in jobs[0].location
        assert "FL" in jobs[0].location

    def test_url_uses_posting_id(self) -> None:
        posting: dict[str, object] = _make_posting(jobPostingId=10383)
        with patch("requests.Session.post", return_value=_mock_response([posting])):
            jobs = LandstarFetcher().fetch()
        assert jobs[0].url == "https://jobs.dayforcehcm.com/en-US/landstar/jobs/JobPosting/10383"

    def test_employment_type_defaults_to_permanent(self) -> None:
        with patch("requests.Session.post", return_value=_mock_response([_make_posting()])):
            jobs = LandstarFetcher().fetch()
        assert jobs[0].employment_type == "permanent"

    def test_required_skills_is_empty_list(self) -> None:
        """Dayforce postings don't surface structured required_skills."""
        with patch("requests.Session.post", return_value=_mock_response([_make_posting()])):
            jobs = LandstarFetcher().fetch()
        assert jobs[0].required_skills == []


class TestLandstarFetcherSalary:
    """Salary parsing from description text."""

    def test_annual_salary_parsed(self) -> None:
        posting: dict[str, object] = _make_posting(
            jobDescription="Salary range: $92,000 - $114,000\nBuild backend services."
        )
        with patch("requests.Session.post", return_value=_mock_response([posting])):
            jobs = LandstarFetcher().fetch()
        assert jobs[0].salary == "$92,000 – $114,000"

    def test_hourly_salary_converted_to_annual(self) -> None:
        """Values < 500 are treated as hourly and multiplied by 2080."""
        posting: dict[str, object] = _make_posting(
            jobDescription="Salary: $18.28 - $22.86 per hour based on experience"
        )
        with patch("requests.Session.post", return_value=_mock_response([posting])):
            jobs = LandstarFetcher().fetch()
        lo: int = int(round(18.28 * 2080))
        hi: int = int(round(22.86 * 2080))
        assert jobs[0].salary == f"${lo:,} – ${hi:,}"

    def test_no_salary_returns_none(self) -> None:
        posting: dict[str, object] = _make_posting(jobDescription="Build cool stuff. No salary listed.")
        with patch("requests.Session.post", return_value=_mock_response([posting])):
            jobs = LandstarFetcher().fetch()
        assert jobs[0].salary is None


class TestLandstarFetcherRemote:
    """Remote detection logic."""

    def test_has_virtual_location_true_sets_remote(self) -> None:
        posting: dict[str, object] = _make_posting(hasVirtualLocation=True)
        with patch("requests.Session.post", return_value=_mock_response([posting])):
            jobs = LandstarFetcher().fetch()
        assert jobs[0].remote is True

    def test_remote_in_description_sets_remote(self) -> None:
        posting: dict[str, object] = _make_posting(
            hasVirtualLocation=False,
            jobDescription="Location: Remote supporting East Coast hours\nSchedule: M-F 8-5",
        )
        with patch("requests.Session.post", return_value=_mock_response([posting])):
            jobs = LandstarFetcher().fetch()
        assert jobs[0].remote is True

    def test_remote_in_title_sets_remote(self) -> None:
        posting: dict[str, object] = _make_posting(jobTitle="Remote Software Engineer", hasVirtualLocation=False)
        with patch("requests.Session.post", return_value=_mock_response([posting])):
            jobs = LandstarFetcher().fetch()
        assert jobs[0].remote is True

    def test_onsite_job_returns_none_for_remote(self) -> None:
        posting: dict[str, object] = _make_posting(
            hasVirtualLocation=False,
            jobDescription="Location: Onsite in Jacksonville, FL\nSchedule: M-F 8-5",
        )
        with patch("requests.Session.post", return_value=_mock_response([posting])):
            jobs = LandstarFetcher().fetch()
        assert jobs[0].remote is None


class TestLandstarFetcherMultiLocation:
    """Jobs posted to multiple locations."""

    def test_multi_location_joined_with_or(self) -> None:
        posting: dict[str, object] = _make_posting(
            postingLocations=[
                {"cityName": "Jacksonville", "stateCode": "FL", "isoCountryCode": "US", "locationId": 1325, "locationType": 1, "formattedAddress": ""},
                {"cityName": "Rockford", "stateCode": "IL", "isoCountryCode": "US", "locationId": 1326, "locationType": 1, "formattedAddress": ""},
            ]
        )
        with patch("requests.Session.post", return_value=_mock_response([posting])):
            jobs = LandstarFetcher().fetch()
        assert "Jacksonville, FL" in jobs[0].location
        assert "Rockford, IL" in jobs[0].location
        assert "or" in jobs[0].location


class TestLandstarFetcherPagination:
    """Pagination: fetcher keeps calling until offset >= maxCount."""

    def test_single_page_when_count_equals_max(self) -> None:
        postings: list[dict[str, object]] = [_make_posting(jobPostingId=i) for i in range(1, 6)]
        with patch("requests.Session.post", return_value=_mock_response(postings, max_count=5)) as mock_post:
            jobs = LandstarFetcher().fetch()
        assert len(jobs) == 5
        assert mock_post.call_count == 1

    def test_skips_postings_with_no_title(self) -> None:
        postings: list[dict[str, object]] = [
            _make_posting(jobPostingId=1, jobTitle="Good Job"),
            _make_posting(jobPostingId=2, jobTitle=""),    # should be skipped
            _make_posting(jobPostingId=3, jobTitle="  "),  # should be skipped
        ]
        with patch("requests.Session.post", return_value=_mock_response(postings)):
            jobs = LandstarFetcher().fetch()
        assert len(jobs) == 1
        assert jobs[0].id == "landstar_1"


class TestLandstarFetcherErrorHandling:
    """Network failures fail open (return empty list, don't raise)."""

    def test_request_exception_returns_empty_list(self) -> None:
        import requests as req
        with patch("requests.Session.post", side_effect=req.exceptions.ConnectionError("down")):
            jobs = LandstarFetcher().fetch()
        assert jobs == []

    def test_http_error_returns_empty_list(self) -> None:
        import requests as req
        mock: MagicMock = MagicMock()
        mock.raise_for_status.side_effect = req.HTTPError("500 Server Error")
        with patch("requests.Session.post", return_value=mock):
            jobs = LandstarFetcher().fetch()
        assert jobs == []
