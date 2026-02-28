import requests
from domain.job import Job


class LeverFetcher:
    BASE_URL = "https://api.lever.co/v0/postings"

    def __init__(self, company: str, company_name: str):
        self.company = company
        self.company_name = company_name

    def fetch(self) -> list[Job]:
        response = requests.get(
            f"{self.BASE_URL}/{self.company}",
            params={"mode": "json"},
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
            jobs.append(Job(
                id=item.get("id", ""),
                title=item.get("text", ""),
                company=self.company_name,
                location=categories.get("location", ""),
                description=item.get("descriptionPlain", ""),
                salary=salary,
                url=item.get("hostedUrl"),
                required_skills=[],
            ))

        return jobs
