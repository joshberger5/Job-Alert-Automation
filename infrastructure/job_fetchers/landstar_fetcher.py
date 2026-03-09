"""
infrastructure/job_fetchers/landstar_fetcher.py
===============================================
Fetches jobs from Landstar System using their Ceridian Dayforce career portal.

Confirmed endpoint (reverse-engineered from careers.landstar.com):
  POST https://jobs.dayforcehcm.com/api/geo/landstar/jobposting/search

Response schema (confirmed from live data):
  {
    "jobPostings": [ { ...posting... } ],
    "maxCount": 18,
    "offset": 0,
    "count": 18
  }

Each posting contains:
  - jobPostingId        (int)   → used as unique ID
  - jobTitle            (str)
  - jobDescription      (str)   → HTML, needs stripping
  - hasVirtualLocation  (bool)  → remote signal
  - postingLocations[]  → list of {cityName, stateCode, isoCountryCode, formattedAddress}
  - postingStartTimestampUTC

Job detail URL pattern (confirmed from Dayforce career site conventions):
  https://jobs.dayforcehcm.com/en-US/landstar/jobs/JobPosting/{jobPostingId}
"""

import logging
import re
from dataclasses import dataclass, field
from typing import ClassVar, cast

import requests

from domain.job import Job

logger: logging.Logger = logging.getLogger(__name__)


def _strip_html(html: str) -> str:
    """Remove HTML tags and decode common entities."""
    text: str = re.sub(r"<[^>]+>", " ", html or "")
    text = (
        text.replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&ndash;", "–")
            .replace("&rsquo;", "'")
            .replace("&ldquo;", '"')
            .replace("&rdquo;", '"')
    )
    return re.sub(r"\s{2,}", " ", text).strip()


@dataclass
class LandstarFetcher:
    """Implements the JobFetcher protocol for Landstar System (Ceridian Dayforce)."""

    SEARCH_URL: ClassVar[str] = "https://jobs.dayforcehcm.com/api/geo/landstar/jobposting/search"
    DETAIL_URL: ClassVar[str] = "https://jobs.dayforcehcm.com/en-US/landstar/jobs/JobPosting/{id}"
    PAGE_SIZE: ClassVar[int] = 100

    company_name: str = field(default="Landstar System", init=False, repr=False)
    _session: requests.Session = field(default_factory=requests.Session, repr=False)
    _total: int = field(default=0, init=False, repr=False)

    def fetch(self) -> list[Job]:
        jobs: list[Job] = []
        offset: int = 0

        while True:
            batch, n_raw = self._fetch_page(offset)
            jobs.extend(batch)
            # Stop if: no items returned, fewer than a full page (last page), or total reached
            if not n_raw or n_raw < self.PAGE_SIZE or len(jobs) >= self._total:
                break
            offset += n_raw

        logger.info("LandstarFetcher: %d jobs fetched", len(jobs))
        return jobs

    def _fetch_page(self, offset: int) -> tuple[list[Job], int]:
        payload: dict[str, int | str] = {
            "jobBoardId": 1,
            "clientNamespace": "landstar",
            "offset": offset,
            "pageSize": self.PAGE_SIZE,
        }
        try:
            resp: requests.Response = self._session.post(
                self.SEARCH_URL,
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("LandstarFetcher request failed (offset=%d): %s", offset, exc)
            return [], 0

        data: dict[str, object] = resp.json()
        self._total = cast(int, data.get("maxCount") or 0)
        raw_postings: list[dict[str, object]] = cast(list[dict[str, object]], data.get("jobPostings") or [])

        jobs: list[Job] = []
        for p in raw_postings:
            job: Job | None = self._parse(p)
            if job:
                jobs.append(job)
        return jobs, len(raw_postings)

    def _parse(self, p: dict[str, object]) -> Job | None:
        posting_id: object = p.get("jobPostingId")
        title: str = str(p.get("jobTitle") or "").strip()
        if not posting_id or not title:
            return None

        description: str = _strip_html(str(p.get("jobDescription") or ""))

        # --- Location ---
        locations: list[dict[str, object]] = cast(list[dict[str, object]], p.get("postingLocations") or [])
        jax: dict[str, object] | None = next(
            (loc for loc in locations if str(loc.get("cityName") or "").lower() == "jacksonville"),
            None,
        )
        primary_loc: dict[str, object] = jax or (locations[0] if locations else {})
        city: str = str(primary_loc.get("cityName") or "")
        state: str = str(primary_loc.get("stateCode") or "")
        location_str: str = f"{city}, {state}".strip(", ") if city or state else ""

        if len(locations) > 1:
            parts: list[str] = [
                f"{str(loc.get('cityName') or '')}, {str(loc.get('stateCode') or '')}".strip(", ")
                for loc in locations
            ]
            location_str = " or ".join(pt for pt in parts if pt)

        # --- Remote ---
        has_virtual: bool = bool(p.get("hasVirtualLocation"))
        desc_lower: str = description.lower()
        title_lower: str = title.lower()
        remote_phrases: tuple[str, ...] = ("remote", "work from home", "100% remote", "fully remote")
        remote: bool | None = (
            True
            if has_virtual or any(ph in desc_lower[:200] or ph in title_lower for ph in remote_phrases)
            else None
        )

        # --- Employment type ---
        if "contract" in desc_lower[:300]:
            employment_type: str = "contract"
        elif "part-time" in desc_lower[:300] or "part time" in desc_lower[:300]:
            employment_type = "part_time"
        else:
            employment_type = "permanent"

        # --- Salary ---
        salary_str: str | None = None
        salary_match: re.Match[str] | None = re.search(
            r"\$\s*([\d,]+(?:\.\d+)?)\s*[-–]\s*\$?\s*([\d,]+(?:\.\d+)?)",
            description[:500],
        )
        if salary_match:
            try:
                lo: float = float(salary_match.group(1).replace(",", ""))
                hi: float = float(salary_match.group(2).replace(",", ""))
                if hi < 500:  # hourly → annual
                    lo *= 2080
                    hi *= 2080
                salary_str = f"${int(round(lo)):,} – ${int(round(hi)):,}"
            except ValueError:
                pass

        url: str = self.DETAIL_URL.format(id=posting_id)
        job_id: str = f"landstar_{posting_id}"

        return Job(
            id=job_id,
            title=title,
            company="Landstar System",
            location=location_str,
            remote=remote,
            employment_type=employment_type,
            description=description,
            url=url,
            salary=salary_str,
            required_skills=[],
        )
