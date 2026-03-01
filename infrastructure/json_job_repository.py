import json
import os
from datetime import datetime
from typing import TypedDict

from domain.job import Job


class _JobEntry(TypedDict):
    first_seen: str
    score: int
    qualified: bool


class JsonJobRepository:

    def __init__(self, path: str = "seen_jobs.json") -> None:
        self._path: str = path
        self._storage: dict[str, _JobEntry] = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self._storage = json.load(f)

    def exists(self, job_id: str) -> bool:
        return job_id in self._storage

    def save(self, job: Job, score: int, qualified: bool) -> None:
        if job.id not in self._storage:
            self._storage[job.id] = {
                "first_seen": datetime.now().isoformat(timespec="seconds"),
                "score": score,
                "qualified": qualified,
            }
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._storage, f, indent=2)

    def get(self, job_id: str) -> _JobEntry:
        return self._storage[job_id]
