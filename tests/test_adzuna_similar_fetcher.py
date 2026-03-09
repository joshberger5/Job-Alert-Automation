"""
tests/test_adzuna_similar_fetcher.py
=====================================
All HTTP is mocked — no network calls are made.
"""

from unittest.mock import MagicMock, call, patch

import pytest

from infrastructure.job_fetchers.adzuna_similar_fetcher import AdzunaSimilarFetcher

# ── HTML helpers ─────────────────────────────────────────────────────────── #

def _seed_api_response(redirect_urls: list[str]) -> MagicMock:
    """Mock the Adzuna search API response with the given redirect URLs."""
    mock: MagicMock = MagicMock()
    mock.raise_for_status.return_value = None
    mock.json.return_value = {
        "results": [{"redirect_url": u} for u in redirect_urls],
        "count": len(redirect_urls),
    }
    return mock


def _detail_page_html(jobs: list[dict[str, str]]) -> str:
    """
    Build an HTML detail page containing a 'Similar jobs' section.

    Each entry in `jobs` should have keys: title, href, company, location, and
    optionally salary (e.g. "$80,000").
    """
    cards: list[str] = []
    for j in jobs:
        salary_html: str = ""
        if j.get("salary"):
            val: str = j["salary"].replace("$", "").replace(",", "")
            salary_html = f'<span>ESTIMATED: <strong>${int(val):,}</strong> per year</span>'
        cards.append(
            f'<div>'
            f'<a href="{j["href"]}">{j["title"]}</a>'
            f'{salary_html}'
            f'<p>{j.get("company", "")}</p>'
            f'<p>{j.get("location", "")}</p>'
            f'</div>'
        )
    section: str = "<h2>Similar jobs</h2>" + "".join(cards)
    return f"<html><body>{section}</body></html>"


def _http_error_response() -> MagicMock:
    import requests as req
    mock: MagicMock = MagicMock()
    mock.raise_for_status.side_effect = req.HTTPError("404 Not Found")
    return mock


def _make_fetcher() -> AdzunaSimilarFetcher:
    return AdzunaSimilarFetcher(app_id="test_id", app_key="test_key")


# ── tests ────────────────────────────────────────────────────────────────── #

class TestAdzunaSimilarFetcherBasic:
    """Core extraction from a seed detail page."""

    def test_similar_jobs_extracted(self) -> None:
        html: str = _detail_page_html([
            {"title": "Java Developer", "href": "https://www.adzuna.com/details/1234567",
             "company": "Acme Corp", "location": "Jacksonville, FL", "salary": "$80,000"},
        ])
        seed_mock: MagicMock = _seed_api_response(["https://www.adzuna.com/details/9999999"])
        detail_mock: MagicMock = MagicMock()
        detail_mock.raise_for_status.return_value = None
        detail_mock.text = html

        with patch("requests.get", side_effect=[seed_mock, detail_mock]):
            jobs = _make_fetcher().fetch()

        assert len(jobs) == 1
        assert jobs[0].title == "Java Developer"
        assert jobs[0].company == "Acme Corp"
        assert jobs[0].location == "Jacksonville, FL"

    def test_id_extracted_from_url(self) -> None:
        html: str = _detail_page_html([
            {"title": "Backend Engineer", "href": "https://www.adzuna.com/details/5646700809",
             "company": "Corp", "location": "Remote"},
        ])
        seed_mock: MagicMock = _seed_api_response(["https://www.adzuna.com/details/9000000"])
        detail_mock: MagicMock = MagicMock()
        detail_mock.raise_for_status.return_value = None
        detail_mock.text = html

        with patch("requests.get", side_effect=[seed_mock, detail_mock]):
            jobs = _make_fetcher().fetch()

        assert jobs[0].id == "5646700809"

    def test_salary_parsed_from_strong_tag(self) -> None:
        html: str = _detail_page_html([
            {"title": "Dev", "href": "https://www.adzuna.com/details/111",
             "company": "X", "location": "NY", "salary": "$82,126"},
        ])
        seed_mock: MagicMock = _seed_api_response(["https://www.adzuna.com/details/9000000"])
        detail_mock: MagicMock = MagicMock()
        detail_mock.raise_for_status.return_value = None
        detail_mock.text = html

        with patch("requests.get", side_effect=[seed_mock, detail_mock]):
            jobs = _make_fetcher().fetch()

        assert jobs[0].salary == "$82,126"

    def test_no_salary_in_html_returns_none(self) -> None:
        html: str = _detail_page_html([
            {"title": "Dev", "href": "https://www.adzuna.com/details/222",
             "company": "X", "location": "NY"},
        ])
        seed_mock: MagicMock = _seed_api_response(["https://www.adzuna.com/details/9000000"])
        detail_mock: MagicMock = MagicMock()
        detail_mock.raise_for_status.return_value = None
        detail_mock.text = html

        with patch("requests.get", side_effect=[seed_mock, detail_mock]):
            jobs = _make_fetcher().fetch()

        assert jobs[0].salary is None

    def test_url_constructed_from_href(self) -> None:
        html: str = _detail_page_html([
            {"title": "Dev", "href": "https://www.adzuna.com/details/333",
             "company": "X", "location": "NY"},
        ])
        seed_mock: MagicMock = _seed_api_response(["https://www.adzuna.com/details/9000000"])
        detail_mock: MagicMock = MagicMock()
        detail_mock.raise_for_status.return_value = None
        detail_mock.text = html

        with patch("requests.get", side_effect=[seed_mock, detail_mock]):
            jobs = _make_fetcher().fetch()

        assert jobs[0].url == "https://www.adzuna.com/details/333"


class TestAdzunaSimilarFetcherDeduplication:
    """Same job ID from multiple seed pages appears only once."""

    def test_duplicates_across_seed_pages_deduped(self) -> None:
        duplicate_job: dict[str, str] = {
            "title": "Java Developer",
            "href": "https://www.adzuna.com/details/1234567",
            "company": "Acme",
            "location": "Jacksonville, FL",
        }
        html: str = _detail_page_html([duplicate_job])

        seed_mock: MagicMock = _seed_api_response([
            "https://www.adzuna.com/details/1111111",
            "https://www.adzuna.com/details/2222222",
        ])
        detail_mock1: MagicMock = MagicMock()
        detail_mock1.raise_for_status.return_value = None
        detail_mock1.text = html

        detail_mock2: MagicMock = MagicMock()
        detail_mock2.raise_for_status.return_value = None
        detail_mock2.text = html

        with patch("requests.get", side_effect=[seed_mock, detail_mock1, detail_mock2]):
            jobs = _make_fetcher().fetch()

        ids: list[str] = [j.id for j in jobs]
        assert ids.count("1234567") == 1


class TestAdzunaSimilarFetcherErrorHandling:
    """Graceful degradation on HTTP errors."""

    def test_http_error_on_seed_page_skipped(self) -> None:
        """A 404 on a seed detail page is silently skipped."""
        seed_mock: MagicMock = _seed_api_response(["https://www.adzuna.com/details/9000000"])
        error_mock: MagicMock = _http_error_response()

        with patch("requests.get", side_effect=[seed_mock, error_mock]):
            jobs = _make_fetcher().fetch()

        assert jobs == []

    def test_seed_api_failure_returns_empty_list(self) -> None:
        import requests as req
        with patch("requests.get", side_effect=req.exceptions.ConnectionError("down")):
            jobs = _make_fetcher().fetch()
        assert jobs == []

    def test_empty_similar_jobs_section_returns_no_jobs(self) -> None:
        html: str = "<html><body><h2>Similar jobs</h2></body></html>"
        seed_mock: MagicMock = _seed_api_response(["https://www.adzuna.com/details/9000000"])
        detail_mock: MagicMock = MagicMock()
        detail_mock.raise_for_status.return_value = None
        detail_mock.text = html

        with patch("requests.get", side_effect=[seed_mock, detail_mock]):
            jobs = _make_fetcher().fetch()

        assert jobs == []

    def test_no_similar_jobs_heading_returns_no_jobs(self) -> None:
        html: str = "<html><body><p>No similar jobs here</p></body></html>"
        seed_mock: MagicMock = _seed_api_response(["https://www.adzuna.com/details/9000000"])
        detail_mock: MagicMock = MagicMock()
        detail_mock.raise_for_status.return_value = None
        detail_mock.text = html

        with patch("requests.get", side_effect=[seed_mock, detail_mock]):
            jobs = _make_fetcher().fetch()

        assert jobs == []
