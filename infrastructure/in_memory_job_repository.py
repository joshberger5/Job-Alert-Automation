from typing import TypedDict

from domain.job import Job


class _JobEntry(TypedDict):
    job: Job
    score: int
    qualified: bool


class InMemoryJobRepository:

    def __init__(self) -> None:
        self._storage: dict[str, _JobEntry] = {}

    def exists(self, job_id: str) -> bool:
        return job_id in self._storage

    def save(self, job: Job, score: int, qualified: bool) -> None:
        self._storage[job.id] = {
            "job": job,
            "score": score,
            "qualified": qualified,
        }

    def get(self, job_id: str) -> Job:
        return self._storage[job_id]["job"]
