import requests
from domain.job import Job


class PhenomFetcher:
    RESULTS_PER_PAGE = 15

    def __init__(self, base_domain: str, org_id: str, company_name: str,
                 keywords: str = "java", location: str = "Jacksonville, FL", distance: int = 50):
        self.base_domain = base_domain
        self.org_id = org_id
        self.company_name = company_name
        self.keywords = keywords
        self.location = location
        self.distance = distance

    def fetch(self) -> list[Job]:
        jobs: list[Job] = []
        page = 1

        while True:
            params: dict[str, str | int] = {
                "Keywords": self.keywords,
                "Location": self.location,
                "Distance": self.distance,
                "CurrentPage": page,
                "RecordsPerPage": self.RESULTS_PER_PAGE,
                "OrganizationIds": self.org_id,
                "SearchType": 1,
                "SortCriteria": 0,
                "SortDirection": 0,
                "ResultsType": 0,
            }
            response = requests.get(
                f"https://{self.base_domain}/search-jobs/results",
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            results = data.get("searchResults", [])
            for item in results:
                city = item.get("city") or item.get("City", "")
                state = item.get("state") or item.get("State", "")
                location_str = ", ".join(filter(None, [city, state]))

                job_id = str(item.get("jobId") or item.get("JobId") or "")
                title = item.get("jobTitle") or item.get("JobTitle") or ""
                description = item.get("jobDescription") or item.get("JobDescription") or ""
                url = item.get("applyUrl") or item.get("ApplyUrl") or f"https://{self.base_domain}/job/{job_id}"

                remote = True if "remote" in location_str.lower() else None

                jobs.append(Job(
                    id=job_id,
                    title=title,
                    company=self.company_name,
                    location=location_str,
                    description=description,
                    salary=None,
                    url=url,
                    required_skills=[],
                    remote=remote,
                    employment_type=None,
                ))

            if len(results) < self.RESULTS_PER_PAGE:
                break
            page += 1

        return jobs
