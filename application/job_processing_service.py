from typing import Iterable

from domain.candidate_profile import CandidateProfile
from domain.events import DomainEvent, JobEvaluated, JobQualified
from domain.filtering_policy import FilteringPolicy
from domain.job import Job
from domain.scoring_policy import ScoringPolicy
from application.event_publisher import EventPublisher
from infrastructure.in_memory_job_repository import InMemoryJobRepository


def _filter_reason(job: Job, profile: CandidateProfile) -> str:
    if not profile.open_to_contract and job.employment_type == "contract":
        return "contract role"
    if profile.remote_allowed and (
        job.remote is True
        or "remote" in job.description.lower()
        or "remote" in job.location.lower()
    ):
        return "remote check failed (should have passed — bug?)"
    return "location mismatch (not remote, not preferred location)"


class JobProcessingService:

    def __init__(
        self,
        repository: InMemoryJobRepository,
        scoring_policy: ScoringPolicy,
        filtering_policy: FilteringPolicy,
        profile: CandidateProfile,
        event_publisher: EventPublisher,
    ) -> None:
        self.repository = repository
        self.scoring_policy = scoring_policy
        self.filtering_policy = filtering_policy
        self.profile = profile
        self.event_publisher = event_publisher

    def process(self, jobs: Iterable[Job]) -> list[dict]:

        emitted_events: list[DomainEvent] = []
        debug_records: list[dict] = []

        for job in jobs:

            record: dict = {
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "remote": job.remote,
                "employment_type": job.employment_type,
                "salary": job.salary,
                "url": job.url,
                "description_length": len(job.description),
            }

            if self.repository.exists(job.id):
                record["result"] = "duplicate"
                debug_records.append(record)
                continue

            if not self.filtering_policy.allows(job, self.profile):
                record["result"] = "filtered_out"
                record["filter_reason"] = _filter_reason(job, self.profile)
                self.repository.save(job, 0, False)
                debug_records.append(record)
                continue

            score, breakdown = self.scoring_policy.evaluate(job, self.profile)
            qualified = self.scoring_policy.qualifies(score)
            self.repository.save(job, score, qualified)

            record["result"] = "qualified" if qualified else "scored_out"
            record["score"] = score
            record["score_breakdown"] = breakdown
            record["qualified"] = qualified

            emitted_events.append(JobEvaluated(job.id, score, qualified))
            if qualified:
                emitted_events.append(JobQualified(job.id, score))

            debug_records.append(record)

        self.event_publisher.publish(emitted_events)
        return debug_records
