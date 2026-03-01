import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

from domain.job import Job

# Regions that are explicitly non-USA — skip these
_EXCLUDED_REGION_FRAGMENTS: tuple[str, ...] = (
    "europe only",
    "europe",
    "uk only",
    "latin america",
    "latam",
    "canada only",
    "australia",
    "asia",
    "africa",
    "no usa",
)


def _is_usa_accessible(region: str) -> bool:
    """Return True when the region does not explicitly exclude USA workers."""
    lower: str = region.strip().lower()
    if not lower:
        return True
    # Accept known inclusive strings immediately
    if lower in ("worldwide", "global", "anywhere", "usa only", "usa", "us only"):
        return True
    # Block if any exclusion fragment matches
    for fragment in _EXCLUDED_REGION_FRAGMENTS:
        if fragment in lower:
            return False
    return True


class WeWorkRemotelyFetcher:
    RSS_URL: str = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
    company_name: str = "We Work Remotely"

    def fetch(self) -> list[Job]:
        response = requests.get(
            self.RSS_URL,
            headers={"User-Agent": "JobAlertBot/1.0 (job-alert-automation)"},
            timeout=15,
        )
        response.raise_for_status()

        root: ET.Element = ET.fromstring(response.text)
        channel: ET.Element | None = root.find("channel")
        if channel is None:
            return []

        # Register the WWR namespace for <region> tag
        ns: dict[str, str] = {"wwr": "https://weworkremotely.com"}

        jobs: list[Job] = []
        for item in channel.findall("item"):
            region_el: ET.Element | None = item.find("wwr:region", ns)
            region: str = (region_el.text or "") if region_el is not None else ""

            if not _is_usa_accessible(region):
                continue

            raw_title: str = (item.findtext("title") or "").strip()
            # Format: "Company Name: Job Title"
            if ": " in raw_title:
                company, title = raw_title.split(": ", 1)
            else:
                company = self.company_name
                title = raw_title

            link: str = (item.findtext("link") or "").strip()
            # Use last path segment as ID
            job_id: str = link.rstrip("/").rsplit("/", 1)[-1] if link else raw_title

            raw_description: str = item.findtext("description") or ""
            description: str = BeautifulSoup(raw_description, "html.parser").get_text(
                separator=" ", strip=True
            )

            location: str = region if region else "Worldwide"

            jobs.append(Job(
                id=job_id,
                title=title,
                company=company,
                location=location,
                description=description,
                salary=None,
                url=link or None,
                required_skills=[],
                remote=True,
                employment_type=None,
            ))

        return jobs
