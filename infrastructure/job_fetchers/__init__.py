from typing import Protocol

from domain.job import Job


class JobFetcher(Protocol):
    company_name: str

    def fetch(self) -> list[Job]:
        ...
