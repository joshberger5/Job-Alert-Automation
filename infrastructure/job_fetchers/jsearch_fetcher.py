import requests
from typing import Any

from domain.job import Job
from infrastructure.job_fetchers._utils import infer_remote

_BASE_URL: str = "https://jsearch.p.rapidapi.com/search"
_HOST: str = "jsearch.p.rapidapi.com"
_REQUEST_TIMEOUT: int = 10


class JSearchFetcher:
    company_name: str = "JSearch"

    def __init__(self, api_key: str, query: str) -> None:
        if not api_key:
            raise ValueError("api_key must not be empty")
        self._api_key: str = api_key
        self._query: str = query

    def fetch(self) -> list[Job]:
        headers: dict[str, str] = {
            "X-RapidAPI-Key": self._api_key,
            "X-RapidAPI-Host": _HOST,
        }
        params: dict[str, str] = {
            "query": self._query,
            "page": "1",
            "num_pages": "1",
            "date_posted": "3days",
        }
        resp: requests.Response = requests.get(
            _BASE_URL, headers=headers, params=params, timeout=_REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        items: list[dict[str, Any]] = data.get("data", [])
        return [self._map_job(item) for item in items]

    def _map_job(self, item: dict[str, Any]) -> Job:
        city: str = item.get("job_city") or ""
        state: str = item.get("job_state") or ""
        location: str = f"{city}, {state}" if city and state else city or state

        job_is_remote: bool | None = item.get("job_is_remote")
        remote: bool | None
        if isinstance(job_is_remote, bool):
            remote = job_is_remote if job_is_remote else infer_remote(location)
        else:
            remote = infer_remote(location)

        max_salary: int | None = item.get("job_max_salary")
        salary: str | None = f"${max_salary:,}" if max_salary is not None else None

        emp_type_raw: str | None = item.get("job_employment_type")
        employment_type: str | None = emp_type_raw.lower() if emp_type_raw else None

        return Job(
            id=str(item.get("job_id", "")),
            title=str(item.get("job_title", "")),
            company=str(item.get("employer_name", "")),
            location=location,
            description=str(item.get("job_description", "")),
            salary=salary,
            url=item.get("job_apply_link"),
            required_skills=[],
            remote=remote,
            employment_type=employment_type,
        )
