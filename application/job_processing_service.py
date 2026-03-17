from typing import Iterable

from domain.candidate_profile import CandidateProfile
from domain.events import DomainEvent, JobEvaluated, JobQualified
from domain.experience_alignment import ExperienceAlignment
from domain.filtering_policy import FilteringPolicy
from domain.job import Job
from domain.scoring_policy import ScoringPolicy
from application.event_publisher import EventPublisher
from application.feedback_bias_service import FeedbackBiasService
from application.job_record import JobRecord
from application.job_repository import JobRepository


def _filter_reason(job: Job, profile: CandidateProfile) -> str:
    if not profile.open_to_contract and job.employment_type == "contract":
        return "contract role"
    if profile.ideal_max_experience_years > 0:
        alignment: ExperienceAlignment = job.experience_requirement().alignment_with(
            profile.ideal_max_experience_years
        )
        if alignment in (ExperienceAlignment.MODERATE_GAP, ExperienceAlignment.LARGE_GAP):
            req_years: int | None = job.experience_requirement().required_years
            return (
                f"experience gap ({req_years} yrs required, "
                f"ideal max {profile.ideal_max_experience_years})"
            )
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
        repository: JobRepository,
        scoring_policy: ScoringPolicy,
        filtering_policy: FilteringPolicy,
        profile: CandidateProfile,
        event_publisher: EventPublisher,
        feedback_bias_service: FeedbackBiasService | None = None,
    ) -> None:
        self.repository: JobRepository = repository
        self.scoring_policy = scoring_policy
        self.filtering_policy = filtering_policy
        self.profile = profile
        self.event_publisher = event_publisher
        self._feedback_bias: FeedbackBiasService = feedback_bias_service or FeedbackBiasService()

    def process(self, jobs: Iterable[Job]) -> list[JobRecord]:

        emitted_events: list[DomainEvent] = []
        debug_records: list[JobRecord] = []

        for job in jobs:

            record: JobRecord = {
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
                if self.filtering_policy.is_unverified_remote(job, self.profile):
                    uv_score: int
                    uv_breakdown: dict[str, int]
                    uv_multiplier: float
                    uv_raw: int
                    uv_raw_breakdown: dict[str, int]
                    uv_raw, uv_raw_breakdown = self.scoring_policy.evaluate(job, self.profile)
                    uv_score, uv_breakdown, uv_multiplier = self._feedback_bias.apply(
                        uv_raw, job.description + " " + job.title, uv_raw_breakdown
                    )
                    self.repository.save(job, uv_score, False)
                    record["result"] = "unverified_remote"
                    record["score"] = uv_score
                    record["score_breakdown"] = uv_breakdown
                    record["feedback_multiplier"] = uv_multiplier
                else:
                    record["result"] = "filtered_out"
                    record["filter_reason"] = _filter_reason(job, self.profile)
                    self.repository.save(job, 0, False)
                debug_records.append(record)
                continue

            score, breakdown = self.scoring_policy.evaluate(job, self.profile)
            final_score: int
            final_breakdown: dict[str, int]
            bias_multiplier: float
            final_score, final_breakdown, bias_multiplier = self._feedback_bias.apply(
                score, job.description + " " + job.title, breakdown
            )
            qualified: bool = self.scoring_policy.qualifies(final_score)
            self.repository.save(job, final_score, qualified)

            record["result"] = "qualified" if qualified else "scored_out"
            record["score"] = final_score
            record["score_breakdown"] = final_breakdown
            record["qualified"] = qualified
            record["feedback_multiplier"] = bias_multiplier

            emitted_events.append(JobEvaluated(job.id, score, qualified))
            if qualified:
                emitted_events.append(JobQualified(job.id, score, job.url or ""))

            debug_records.append(record)

        self.event_publisher.publish(emitted_events)
        return debug_records
