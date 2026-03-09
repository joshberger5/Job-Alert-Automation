"""
infrastructure/job_fetchers/adzuna_similar_fetcher.py
======================================================
Fetches "Similar jobs" from Adzuna detail pages.

Strategy:
  1. Call the Adzuna search API to collect up to `seed_limit` seed job URLs.
  2. Fetch each seed's detail page in parallel (ThreadPoolExecutor).
  3. Parse the "Similar jobs" section from each detail page using BeautifulSoup.
  4. Deduplicate by job ID across all seed pages and return a flat list[Job].

HTML pattern confirmed from live Adzuna detail pages:
  <h2>Similar jobs</h2>
  <div>
    <a href="https://www.adzuna.com/details/5646700809">Senior Java Developer</a>
    <span>ESTIMATED: <strong>$82,126</strong> per year</span>
    <p>Intercontinental Exchange</p>
    <p>Jacksonville, Florida</p>
  </div>
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from typing import cast

from bs4 import BeautifulSoup, Tag

from domain.job import Job
from infrastructure.job_fetchers._utils import infer_remote

logger: logging.Logger = logging.getLogger(__name__)

_DETAIL_TIMEOUT: int = 10
_DETAIL_WORKERS: int = 10


class AdzunaSimilarFetcher:
    BASE_URL: str = "https://api.adzuna.com/v1/api/jobs/us/search"
    company_name: str = "Adzuna (Similar)"

    def __init__(
        self,
        app_id: str,
        app_key: str,
        keywords: str = "java",
        location: str = "Jacksonville FL",
        max_days_old: int = 1,
        seed_limit: int = 15,
    ) -> None:
        self.app_id: str = app_id
        self.app_key: str = app_key
        self.keywords: str = keywords
        self.location: str = location
        self.max_days_old: int = max_days_old
        self.seed_limit: int = seed_limit

    def fetch(self) -> list[Job]:
        seed_urls: list[str] = self._get_seed_urls()

        similar_jobs: dict[str, Job] = {}
        with ThreadPoolExecutor(max_workers=_DETAIL_WORKERS) as executor:
            futures = {executor.submit(self._scrape_similar, url): url for url in seed_urls}
            for future in as_completed(futures):
                for job in future.result():
                    if job.id not in similar_jobs:
                        similar_jobs[job.id] = job

        return list(similar_jobs.values())

    def _get_seed_urls(self) -> list[str]:
        params: dict[str, str | int] = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "what": self.keywords,
            "where": self.location,
            "distance": 25,
            "max_days_old": self.max_days_old,
            "results_per_page": min(self.seed_limit, 50),
            "content-type": "application/json",
        }
        try:
            response: requests.Response = requests.get(
                f"{self.BASE_URL}/1",
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            data: dict[str, object] = response.json()
            results: list[dict[str, object]] = cast(list[dict[str, object]], data.get("results") or [])
            urls: list[str] = [
                str(item.get("redirect_url", ""))
                for item in results
                if item.get("redirect_url")
            ]
            return urls[: self.seed_limit]
        except requests.RequestException as exc:
            logger.warning("AdzunaSimilarFetcher seed request failed: %s", exc)
            return []

    def _scrape_similar(self, url: str) -> list[Job]:
        """Fetch a seed detail page and extract its 'Similar jobs' section."""
        try:
            resp: requests.Response = requests.get(
                url,
                timeout=_DETAIL_TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.debug("AdzunaSimilarFetcher: failed to fetch %s: %s", url, exc)
            return []

        soup: BeautifulSoup = BeautifulSoup(resp.text, "html.parser")
        return self._parse_similar_section(soup)

    def _parse_similar_section(self, soup: BeautifulSoup) -> list[Job]:
        """Find the 'Similar jobs' heading and extract all job links beneath it."""
        heading: Tag | None = None
        for h2 in soup.find_all("h2"):
            if "similar jobs" in h2.get_text(strip=True).lower():
                heading = h2
                break
        if heading is None:
            return []

        jobs: list[Job] = []
        seen_ids: set[str] = set()

        for raw_elem in heading.find_all_next("a", href=re.compile(r"/details/\d+")):
            link: Tag = cast(Tag, raw_elem)
            href: str = str(link.get("href", ""))
            suffix: str = href.split("/details/")[-1] if "/details/" in href else href
            id_match: re.Match[str] | None = re.search(r"^\d+", suffix)
            if not id_match:
                continue

            job_id: str = id_match.group(0)
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            job: Job | None = self._extract_job(link, job_id, href)
            if job:
                jobs.append(job)

        return jobs

    def _extract_job(self, link: Tag, job_id: str, href: str) -> Job | None:
        """Extract job fields from a similar-jobs link and its parent container."""
        title: str = link.get_text(strip=True)
        if not title:
            return None

        raw_parent = link.parent
        container: Tag | None = raw_parent if isinstance(raw_parent, Tag) else None

        salary: str | None = None
        company: str = ""
        location_str: str = ""

        if container is not None:
            found_strong = container.find("strong")
            strong: Tag | None = found_strong if isinstance(found_strong, Tag) else None
            if strong is not None:
                raw: str = strong.get_text(strip=True).replace("$", "").replace(",", "").strip()
                if raw.isdigit():
                    salary = f"${int(raw):,}"

            all_texts: list[str] = [t.strip() for t in container.stripped_strings if t.strip()]
            filtered: list[str] = [
                t for t in all_texts
                if t != title and not re.match(r"ESTIMATED|per year|\$", t)
            ]
            if filtered:
                company = filtered[0]
            if len(filtered) > 1:
                location_str = filtered[1]

        url: str = href if href.startswith("http") else f"https://www.adzuna.com{href}"

        return Job(
            id=job_id,
            title=title,
            company=company,
            location=location_str,
            description="",
            salary=salary,
            url=url,
            required_skills=[],
            remote=infer_remote(location_str),
            employment_type=None,
        )
