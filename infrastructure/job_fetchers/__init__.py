from typing import Protocol

from domain.job import Job


class JobFetcher(Protocol):
    def fetch(self) -> list[Job]:
        ...
