import requests
from domain.job import Job
from infrastructure.job_fetchers._utils import infer_remote


class AdzunaFetcher:
    BASE_URL = "https://api.adzuna.com/v1/api/jobs/us/search"
    company_name: str = "Adzuna"

    def __init__(
        self,
        app_id: str,
        app_key: str,
        keywords: str = "java",
        location: str = "Jacksonville FL",
        max_days_old: int = 1,
    ):
        self.app_id = app_id
        self.app_key = app_key
        self.keywords = keywords
        self.location = location
        self.max_days_old = max_days_old

    def fetch(self) -> list[Job]:
        jobs: list[Job] = []
        page = 1

        while True:
            params: dict[str, str | int] = {
                "app_id": self.app_id,
                "app_key": self.app_key,
                "what": self.keywords,
                "where": self.location,
                "distance": 25,
                "max_days_old": self.max_days_old,
                "results_per_page": 50,
                "content-type": "application/json",
            }
            response = requests.get(
                f"{self.BASE_URL}/{page}",
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            for item in results:
                salary_min = item.get("salary_min")
                salary_max = item.get("salary_max")
                if salary_min is not None and salary_max is not None:
                    if salary_min == salary_max:
                        salary = f"${int(salary_min):,}"
                    else:
                        salary = f"${int(salary_min):,} - ${int(salary_max):,}"
                elif salary_min is not None:
                    salary = f"${int(salary_min):,}"
                elif salary_max is not None:
                    salary = f"${int(salary_max):,}"
                else:
                    salary = None

                location_display = item.get("location", {}).get("display_name", "")
                remote: bool | None = infer_remote(location_display)

                contract_type = item.get("contract_type") or ""
                contract_time = item.get("contract_time") or ""
                if contract_type == "permanent" or contract_time == "full_time":
                    employment_type = "full-time"
                elif contract_type == "contract":
                    employment_type = "contract"
                elif contract_time == "part_time":
                    employment_type = "part-time"
                else:
                    employment_type = None

                jobs.append(Job(
                    id=str(item.get("id", "")),
                    title=item.get("title", ""),
                    company=item.get("company", {}).get("display_name", ""),
                    location=location_display,
                    description=item.get("description", ""),
                    salary=salary,
                    url=item.get("redirect_url"),
                    required_skills=[],
                    remote=remote,
                    employment_type=employment_type,
                ))

            # Stop if we got fewer than a full page (no more pages)
            if len(results) < 50:
                break
            page += 1

        return jobs
