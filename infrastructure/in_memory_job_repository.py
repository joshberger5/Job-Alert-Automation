class InMemoryJobRepository:

    def __init__(self):
        self._storage = {}

    def exists(self, job_id: str) -> bool:
        return job_id in self._storage

    def save(self, job, score: int, qualified: bool):
        self._storage[job.id] = {
            "job": job,
            "score": score,
            "qualified": qualified
        }

    def get(self, job_id: str):
        return self._storage[job_id]["job"]