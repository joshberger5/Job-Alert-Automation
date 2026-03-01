from typing import Protocol

from domain.job import Job


class JobRepository(Protocol):
    def exists(self, job_id: str) -> bool: ...
    def save(self, job: Job, score: int, qualified: bool) -> None: ...
