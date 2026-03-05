from typing import Any

import requests
from bs4 import BeautifulSoup

from domain.job import Job
from infrastructure.job_fetchers._utils import infer_remote


class GreenhouseFetcher:
    BASE: str = "https://boards-api.greenhouse.io/v1/boards"

    def __init__(self, company: str, company_name: str) -> None:
        self.company: str = company
        self.company_name: str = company_name

    def fetch(self) -> list[Job]:
        response = requests.get(
            f"{self.BASE}/{self.company}/jobs",
            params={"content": "true"},
            timeout=15,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()

        jobs: list[Job] = []
        for item in data.get("jobs", []):
            job_id: str = str(item.get("id", ""))
            title: str = item.get("title", "")
            location_obj: dict[str, Any] = item.get("location") or {}
            location: str = location_obj.get("name", "")
            url: str = item.get("absolute_url", "")
            remote: bool | None = infer_remote(location)

            content_html: str = item.get("content", "") or ""
            description: str = BeautifulSoup(content_html, "html.parser").get_text(
                separator=" ", strip=True
            )

            jobs.append(Job(
                id=job_id,
                title=title,
                company=self.company_name,
                location=location,
                description=description,
                salary=None,
                url=url,
                required_skills=[],
                remote=remote,
                employment_type=None,
            ))

        return jobs
