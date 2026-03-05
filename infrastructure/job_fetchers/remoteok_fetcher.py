from typing import Any

import requests
from bs4 import BeautifulSoup

from domain.job import Job


class RemoteOKFetcher:
    API_URL: str = "https://remoteok.com/api"
    company_name: str = "RemoteOK"

    def __init__(self, tags: str = "java") -> None:
        self.tags: str = tags

    def fetch(self) -> list[Job]:
        response = requests.get(
            self.API_URL,
            params={"tags": self.tags},
            headers={"User-Agent": "JobAlertBot/1.0 (job-alert-automation)"},
            timeout=15,
        )
        response.raise_for_status()
        items: list[Any] = response.json()

        jobs: list[Job] = []
        # First element is metadata — skip it
        for item in items[1:]:
            if not isinstance(item, dict):
                continue

            job_id: str = str(item.get("id", ""))
            title: str = item.get("position", "")
            company: str = item.get("company", "")
            location: str = item.get("location", "") or "Worldwide"
            url: str = item.get("url", "")

            raw_description: str = item.get("description", "") or ""
            description: str = BeautifulSoup(raw_description, "html.parser").get_text(
                separator=" ", strip=True
            )

            tags: list[str] = item.get("tags", []) or []

            jobs.append(Job(
                id=job_id,
                title=title,
                company=company,
                location=location,
                description=description,
                salary=None,
                url=url,
                required_skills=tags,
                remote=True,
                employment_type=None,
            ))

        return jobs
