import requests
from domain.job import Job


class WorkdayFetcher:
    LIMIT = 20

    def __init__(self, base_url: str, tenant: str, company: str,
                 company_name: str, recruiting_base: str,
                 search_text: str = "java"):
        self.base_url = base_url
        self.tenant = tenant
        self.company = company
        self.company_name = company_name
        self.recruiting_base = recruiting_base
        self.search_text = search_text

    def fetch(self) -> list[Job]:
        jobs: list[Job] = []
        offset = 0

        while True:
            response = requests.post(
                f"{self.base_url}/wday/cxs/{self.tenant}/{self.company}/jobs",
                json={
                    "appliedFacets": {},
                    "limit": self.LIMIT,
                    "offset": offset,
                    "searchText": self.search_text,
                },
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            postings = data.get("jobPostings", [])
            for item in postings:
                bullet_fields = item.get("bulletFields") or []
                job_id = bullet_fields[0] if bullet_fields else ""
                external_path = item.get("externalPath", "")
                url = f"{self.recruiting_base}{external_path}" if external_path else None

                jobs.append(Job(
                    id=job_id,
                    title=item.get("title", ""),
                    company=self.company_name,
                    location=item.get("locationsText", ""),
                    description="",
                    salary=None,
                    url=url,
                    required_skills=[],
                ))

            if len(postings) < self.LIMIT:
                break
            offset += self.LIMIT

        return jobs
