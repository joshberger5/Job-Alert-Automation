import json
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

from domain.job import Job


_EMPLOYMENT_TYPE_MAP: dict[str, str] = {
    "FULL_TIME": "full-time",
    "PART_TIME": "part-time",
    "CONTRACTOR": "contract",
    "TEMPORARY": "contract",
    "INTERN": "internship",
}


def _map_employment_type(raw: str) -> str | None:
    return _EMPLOYMENT_TYPE_MAP.get(raw.upper())

_BASE_HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

_DETAIL_TIMEOUT: int = 8
_DETAIL_WORKERS: int = 10


class IcimsFetcher:
    """Fetches jobs from an iCIMS-powered career portal."""

    _PAGE_SIZE: int = 10

    def __init__(self, base_url: str, company_name: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.company_name = company_name

    def fetch(self) -> list[Job]:
        job_stubs: list[tuple[str, str, str]] = self._fetch_all_stubs()

        def build_job(stub: tuple[str, str, str]) -> Job:
            job_id, title, relative_url = stub
            detail_url: str = f"{self.base_url}{relative_url}"
            location, description = self._fetch_detail(detail_url)
            remote: bool | None = True if "remote" in location.lower() else None
            return Job(
                id=job_id,
                title=title,
                company=self.company_name,
                location=location,
                description=description,
                salary=None,
                url=detail_url,
                required_skills=[],
                remote=remote,
                employment_type=None,
            )

        jobs: list[Job] = []
        with ThreadPoolExecutor(max_workers=_DETAIL_WORKERS) as pool:
            futures = {pool.submit(build_job, stub): stub for stub in job_stubs}
            for future in as_completed(futures):
                try:
                    jobs.append(future.result())
                except Exception:
                    pass
        return jobs

    def _fetch_all_stubs(self) -> list[tuple[str, str, str]]:
        """Returns (job_id, title, relative_url) for every listing page."""
        stubs: list[tuple[str, str, str]] = []
        startrow: int = 0
        while True:
            params: dict[str, str | int] = {
                "q": "",
                "sortColumn": "referencedate",
                "sortDirection": "desc",
                "startrow": startrow,
            }
            response = requests.get(
                f"{self.base_url}/tile-search-results/",
                params=params,
                headers=_BASE_HEADERS,
                timeout=15,
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            tiles = soup.select("li.job-tile[data-url]")
            if not tiles:
                break
            for tile in tiles:
                relative_url: str = tile["data-url"]
                anchor = tile.select_one("a.jobTitle-link")
                title: str = anchor.get_text(strip=True) if anchor else ""
                id_match = re.search(r"/(\d+)/?$", relative_url)
                job_id: str = id_match.group(1) if id_match else relative_url
                stubs.append((job_id, title, relative_url))
            if len(tiles) < self._PAGE_SIZE:
                break
            startrow += self._PAGE_SIZE
        return stubs

    def _fetch_detail(self, url: str) -> tuple[str, str]:
        """Returns (location, plain_text_description) for a job detail page."""
        try:
            response = requests.get(url, headers=_BASE_HEADERS, timeout=_DETAIL_TIMEOUT)
            response.raise_for_status()
        except requests.RequestException:
            return "", ""
        soup = BeautifulSoup(response.text, "html.parser")

        geo = soup.select_one("span.jobGeoLocation")
        location: str = geo.get_text(strip=True) if geo else ""

        desc_tag = soup.select_one("span[itemprop='description']")
        description: str = desc_tag.get_text(separator=" ", strip=True) if desc_tag else ""

        return location, description


class IcimsSitemapFetcher:
    """Fetches jobs from older iCIMS portals whose job data is JavaScript-rendered.

    Uses the sitemap.xml to discover job URLs, then reads JSON-LD from each
    detail page (which is server-rendered when ?in_iframe=1 is appended).
    """

    _SITEMAP_NS: str = "http://www.sitemaps.org/schemas/sitemap/0.9"

    def __init__(
        self,
        base_url: str,
        company_name: str,
        location_filter: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.company_name = company_name
        self.location_filter: str | None = location_filter.lower() if location_filter else None

    def fetch(self) -> list[Job]:
        job_urls: list[str] = self._fetch_sitemap()
        jobs: list[Job] = []
        with ThreadPoolExecutor(max_workers=_DETAIL_WORKERS) as pool:
            futures = {pool.submit(self._fetch_job, url): url for url in job_urls}
            for future in as_completed(futures):
                try:
                    job: Job | None = future.result()
                    if job is not None:
                        jobs.append(job)
                except Exception:
                    pass
        return jobs

    def _fetch_sitemap(self) -> list[str]:
        response = requests.get(
            f"{self.base_url}/sitemap.xml",
            headers=_BASE_HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        root: ET.Element = ET.fromstring(response.text)
        ns: dict[str, str] = {"sm": self._SITEMAP_NS}
        return [
            el.text
            for el in root.findall("sm:url/sm:loc", ns)
            if el.text and "/jobs/" in el.text and el.text.endswith("/job")
        ]

    def _fetch_job(self, url: str) -> Job | None:
        try:
            response = requests.get(
                f"{url}?in_iframe=1",
                headers=_BASE_HEADERS,
                timeout=_DETAIL_TIMEOUT,
            )
            response.raise_for_status()
        except requests.RequestException:
            return None

        soup: BeautifulSoup = BeautifulSoup(response.text, "html.parser")
        ld_tag = soup.find("script", {"type": "application/ld+json"})
        if not ld_tag or not ld_tag.string:
            return None

        try:
            data: dict = json.loads(ld_tag.string)
        except json.JSONDecodeError:
            return None

        if data.get("@type") != "JobPosting":
            return None

        location: str = self._extract_location(data)

        if self.location_filter and self.location_filter not in location.lower():
            return None

        id_match = re.search(r"/jobs/(\d+)/", url)
        job_id: str = id_match.group(1) if id_match else url

        title: str = data.get("title", "")

        desc_html: str = data.get("description", "")
        description: str = BeautifulSoup(desc_html, "html.parser").get_text(
            separator=" ", strip=True
        )

        remote: bool | None = True if "remote" in location.lower() else None
        employment_type: str | None = _map_employment_type(data.get("employmentType", ""))

        return Job(
            id=job_id,
            title=title,
            company=self.company_name,
            location=location,
            description=description,
            salary=None,
            url=url,
            required_skills=[],
            remote=remote,
            employment_type=employment_type,
        )

    @staticmethod
    def _extract_location(data: dict) -> str:
        locations: list[dict] | dict = data.get("jobLocation", [])
        if isinstance(locations, dict):
            locations = [locations]
        if not locations:
            return ""
        addr: dict = locations[0].get("address", {})
        city: str = addr.get("addressLocality", "")
        state: str = addr.get("addressRegion", "")
        country: str = addr.get("addressCountry", "")
        return ", ".join(part for part in [city, state, country] if part)
