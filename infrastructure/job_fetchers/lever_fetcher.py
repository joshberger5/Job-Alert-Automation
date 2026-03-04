import requests
from domain.job import Job
from infrastructure.job_fetchers._utils import infer_remote


class LeverFetcher:
    BASE_URL = "https://api.lever.co/v0/postings"

    def __init__(self, company: str, company_name: str, location: str | None = None) -> None:
        self.company: str = company
        self.company_name: str = company_name
        self.location: str | None = location

    def fetch(self) -> list[Job]:
        params: dict[str, str] = {"mode": "json"}
        if self.location is not None:
            params["location"] = self.location
        response = requests.get(
            f"{self.BASE_URL}/{self.company}",
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        jobs = []
        for item in data:
            salary_range = item.get("salaryRange") or {}
            salary_min = salary_range.get("min")
            salary_max = salary_range.get("max")
            if salary_min is not None and salary_max is not None:
                salary = f"${int(salary_min):,} - ${int(salary_max):,}"
            elif salary_min is not None:
                salary = f"${int(salary_min):,}"
            elif salary_max is not None:
                salary = f"${int(salary_max):,}"
            else:
                salary = None

            categories = item.get("categories") or {}

            location_str = categories.get("location", "")
            remote: bool | None = infer_remote(location_str)

            commitment = (categories.get("commitment") or "").lower()
            if "full" in commitment:
                employment_type = "full-time"
            elif "contract" in commitment:
                employment_type = "contract"
            elif "part" in commitment:
                employment_type = "part-time"
            elif "intern" in commitment:
                employment_type = "internship"
            else:
                employment_type = None

            jobs.append(Job(
                id=item.get("id", ""),
                title=item.get("text", ""),
                company=self.company_name,
                location=location_str,
                description=item.get("descriptionPlain", ""),
                salary=salary,
                url=item.get("hostedUrl"),
                required_skills=[],
                remote=remote,
                employment_type=employment_type,
            ))

        return jobs
