"""Tests for OracleFetcher (red until Plan 02-04 is implemented)."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from infrastructure.job_fetchers.oracle_fetcher import OracleFetcher
from domain.job import Job


_FIXTURE_PATH: Path = Path(__file__).parent / "fixtures" / "oracle_response.json"


def _load_fixture() -> dict[str, object]:
    with open(_FIXTURE_PATH, encoding="utf-8") as f:
        result: dict[str, object] = json.load(f)
        return result


def _mock_response(data: dict[str, object]) -> MagicMock:
    resp: MagicMock = MagicMock()
    resp.json.return_value = data
    resp.raise_for_status.return_value = None
    resp.text = ""
    return resp


def test_oracle_happy_path() -> None:
    """Mock requests.get to return fixture → returns list[Job]."""
    fixture: dict[str, object] = _load_fixture()

    # Detail page mock returns empty description
    detail_resp: MagicMock = MagicMock()
    detail_resp.raise_for_status.return_value = None
    detail_resp.text = "<html><body></body></html>"

    with patch("requests.get", side_effect=[_mock_response(fixture), detail_resp]):
        fetcher: OracleFetcher = OracleFetcher(
            base_url="https://jpmc.fa.oraclecloud.com",
            site_id="CX_1001",
            company_name="JPMorgan Chase",
            keyword="java",
        )
        jobs: list[Job] = fetcher.fetch()

    assert len(jobs) == 1
    assert jobs[0].title == "Software Engineer III"
    assert jobs[0].company == "JPMorgan Chase"


def test_oracle_paginates() -> None:
    """OracleFetcher fetches page 2 when hasMore=True on page 1."""
    page1: dict[str, object] = {
        "count": 1,
        "hasMore": True,
        "offset": 0,
        "limit": 25,
        "items": [{"requisitionList": [{"Id": "111", "Title": "Job A", "PrimaryLocation": "NY"}]}],
    }
    page2: dict[str, object] = {
        "count": 1,
        "hasMore": False,
        "offset": 25,
        "limit": 25,
        "items": [{"requisitionList": [{"Id": "222", "Title": "Job B", "PrimaryLocation": "FL"}]}],
    }
    detail_resp: MagicMock = MagicMock()
    detail_resp.raise_for_status.return_value = None
    detail_resp.text = "<html><body></body></html>"

    with patch(
        "requests.get",
        side_effect=[_mock_response(page1), _mock_response(page2), detail_resp, detail_resp],
    ):
        fetcher: OracleFetcher = OracleFetcher(
            base_url="https://jpmc.fa.oraclecloud.com",
            site_id="CX_1001",
            company_name="JPMorgan Chase",
            keyword="java",
        )
        jobs: list[Job] = fetcher.fetch()

    assert len(jobs) == 2


def test_oracle_field_mapping() -> None:
    """Id→id, Title→title, PrimaryLocation→location."""
    fixture: dict[str, object] = _load_fixture()
    detail_resp: MagicMock = MagicMock()
    detail_resp.raise_for_status.return_value = None
    detail_resp.text = "<html><body></body></html>"

    with patch("requests.get", side_effect=[_mock_response(fixture), detail_resp]):
        fetcher: OracleFetcher = OracleFetcher(
            base_url="https://jpmc.fa.oraclecloud.com",
            site_id="CX_1001",
            company_name="JPMorgan Chase",
            keyword="java",
        )
        jobs: list[Job] = fetcher.fetch()

    assert jobs[0].id == "210672475"
    assert jobs[0].title == "Software Engineer III"
    assert "Jersey City" in jobs[0].location
