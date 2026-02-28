from typing import Iterable

from domain.candidate_profile import CandidateProfile
from domain.events import DomainEvent, JobEvaluated, JobQualified
from domain.filtering_policy import FilteringPolicy
from domain.job import Job
from domain.scoring_policy import ScoringPolicy
from application.event_publisher import EventPublisher
from infrastructure.in_memory_job_repository import InMemoryJobRepository


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

    def process(self, jobs: Iterable[Job]) -> None:

        emitted_events: list[DomainEvent] = []

        for job in jobs:

            if self.repository.exists(job.id):
                continue

            if not self.filtering_policy.allows(job, self.profile):
                self.repository.save(job, 0, False)
                continue

            score, _ = self.scoring_policy.evaluate(
                job,
                self.profile
            )

            qualified = self.scoring_policy.qualifies(score)

            self.repository.save(job, score, qualified)

            emitted_events.append(
                JobEvaluated(job.id, score, qualified)
            )

            if qualified:
                emitted_events.append(
                    JobQualified(job.id, score)
                )

        self.event_publisher.publish(emitted_events)
