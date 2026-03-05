import re
from typing import Any

import requests
from domain.job import Job


class PhenomFetcher:
    RESULTS_PER_PAGE = 15

    def __init__(self, base_domain: str, org_id: str, company_name: str,
                 keywords: str = "java",
                 latitude: float | None = None,
                 longitude: float | None = None,
                 radius: int = 50) -> None:
        self.base_domain: str = base_domain
        self.org_id: str = org_id
        self.company_name: str = company_name
        self.keywords: str = keywords
        self.latitude: float | None = latitude
        self.longitude: float | None = longitude
        self.radius: int = radius

    def fetch(self) -> list[Job]:
        jobs: list[Job] = []
        page: int = 1

        while True:
            params: dict[str, str | int | float] = {
                "Keywords": self.keywords,
                "CurrentPage": page,
                "RecordsPerPage": self.RESULTS_PER_PAGE,
                "OrganizationIds": self.org_id,
                "SearchType": 1,
                "SortCriteria": 0,
                "SortDirection": 0,
                "ResultsType": 0,
            }
            if self.latitude is not None and self.longitude is not None:
                params["Latitude"] = self.latitude
                params["Longitude"] = self.longitude
                params["Radius"] = self.radius
            response = requests.get(
                f"https://{self.base_domain}/search-jobs/results",
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()

            results_html: str = data.get("results", "")
            has_content: bool = data.get("hasContent", True)

            if page == 1:
                top_keys: list[str] = list(data.keys())
                print(f"  [PhenomFetcher:{self.company_name}] page-1 keys={top_keys} hasContent={has_content} results[:200]={results_html[:200]!r}")

            links: list[str] = re.findall(r'href="(/job/[^"]+)"', results_html)

            if not results_html.strip():
                print(f"  [PhenomFetcher:{self.company_name}] WARNING: empty results HTML on page {page}")

            for href in links:
                parts: list[str] = href.strip("/").split("/")
                # parts: ["job", city, title-slug, company-id, job-id]
                if len(parts) < 5:
                    continue
                job_id: str = parts[-1]
                title: str = parts[-3].replace("-", " ").title()
                location: str = parts[1].replace("-", " ").title()
                url: str = f"https://{self.base_domain}{href}"
                remote: bool | None = True if "remote" in location.lower() else None

                jobs.append(Job(
                    id=job_id,
                    title=title,
                    company=self.company_name,
                    location=location,
                    description="",
                    salary=None,
                    url=url,
                    required_skills=[],
                    remote=remote,
                    employment_type=None,
                ))

            if len(links) < self.RESULTS_PER_PAGE:
                break
            page += 1

        return jobs
