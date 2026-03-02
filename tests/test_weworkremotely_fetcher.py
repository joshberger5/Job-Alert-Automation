from pathlib import Path
from unittest.mock import MagicMock, patch

from infrastructure.job_fetchers.weworkremotely_fetcher import WeWorkRemotelyFetcher

FIXTURES: Path = Path(__file__).parent / "fixtures"


def _mock_response(rss_text: str, status: int = 200) -> MagicMock:
    m: MagicMock = MagicMock()
    m.status_code = status
    m.raise_for_status = MagicMock()
    m.text = rss_text
    return m


def _load_fixture() -> str:
    return (FIXTURES / "weworkremotely_response.rss").read_text()


def test_happy_path() -> None:
    rss: str = _load_fixture()
    with patch("requests.get", return_value=_mock_response(rss)):
        jobs = WeWorkRemotelyFetcher().fetch()

    # fixture has 3 items; "Europe Only" is filtered → 2 jobs
    assert len(jobs) == 2

    j = jobs[0]
    assert j.company == "GoFasti"
    assert j.title == "Product Designer"
    assert j.location == "Anywhere in the World"
    assert j.remote is True
    assert j.url == "https://weworkremotely.com/remote-jobs/gofasti-product-designer"
    assert j.id == "gofasti-product-designer"


def test_region_filtering() -> None:
    rss: str = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:wwr="https://weworkremotely.com">
  <channel>
    <item>
      <title>CompA: DevA</title>
      <wwr:region>Worldwide</wwr:region>
      <description></description>
      <link>https://weworkremotely.com/remote-jobs/comp-a-dev-a</link>
    </item>
    <item>
      <title>CompB: DevB</title>
      <wwr:region>Europe Only</wwr:region>
      <description></description>
      <link>https://weworkremotely.com/remote-jobs/comp-b-dev-b</link>
    </item>
    <item>
      <title>CompC: DevC</title>
      <wwr:region></wwr:region>
      <description></description>
      <link>https://weworkremotely.com/remote-jobs/comp-c-dev-c</link>
    </item>
  </channel>
</rss>"""
    with patch("requests.get", return_value=_mock_response(rss)):
        jobs = WeWorkRemotelyFetcher().fetch()

    # "Europe Only" filtered; "Worldwide" and "" kept
    assert len(jobs) == 2
    titles: list[str] = [j.title for j in jobs]
    assert "DevA" in titles
    assert "DevC" in titles
    assert "DevB" not in titles


def test_no_colon_in_title() -> None:
    rss: str = _load_fixture()
    with patch("requests.get", return_value=_mock_response(rss)):
        jobs = WeWorkRemotelyFetcher().fetch()

    # item 3 in fixture: title="Software Engineer" (no colon) → company fallback
    no_colon_jobs = [j for j in jobs if j.title == "Software Engineer"]
    assert len(no_colon_jobs) == 1
    assert no_colon_jobs[0].company == "We Work Remotely"
    assert no_colon_jobs[0].location == "Worldwide"  # empty region → Worldwide


def test_html_description() -> None:
    rss: str = _load_fixture()
    with patch("requests.get", return_value=_mock_response(rss)):
        jobs = WeWorkRemotelyFetcher().fetch()

    # GoFasti item description has HTML entities that BS4 decodes and strips
    gofasti_jobs: list = [j for j in jobs if j.company == "GoFasti"]
    assert len(gofasti_jobs) == 1
    assert "<" not in gofasti_jobs[0].description
    assert "web applications" in gofasti_jobs[0].description
