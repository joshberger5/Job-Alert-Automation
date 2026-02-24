from domain.job import Job
from domain.candidate_profile import CandidateProfile
from domain.filtering_policy import FilteringPolicy
from domain.scoring_policy import ScoringPolicy
from domain.events import JobQualified

from application.job_processing_service import JobProcessingService
from application.resume_profile_builder import ResumeProfileBuilder
from application.simple_event_dispatcher import SimpleEventDispatcher

from infrastructure.in_memory_job_repository import InMemoryJobRepository
from infrastructure.in_memory_event_publisher import InMemoryEventPublisher
from infrastructure.resume.pdf_resume_parser import PdfResumeParser


def job_qualified_handler(event):
    print(f"\n🎉 JOB QUALIFIED: {event.job_id} | Score: {event.score}")


def main():

    parser = PdfResumeParser()
    resume_text = parser.extract_text("resume.pdf")

    builder = ResumeProfileBuilder()
    profile = builder.build(resume_text)

    print(profile)

    repository = InMemoryJobRepository()
    filtering_policy = FilteringPolicy()
    scoring_policy = ScoringPolicy()

    dispatcher = SimpleEventDispatcher()
    dispatcher.register(JobQualified, job_qualified_handler)

    publisher = InMemoryEventPublisher(dispatcher)

    service = JobProcessingService(
        repository=repository,
        scoring_policy=scoring_policy,
        filtering_policy=filtering_policy,
        profile=profile,
        event_publisher=publisher
    )

    sample_jobs = [
        Job(
            id="1",
            title="Java Backend Engineer",
            company="Acme",
            location="Jacksonville",
            description="3 years experience with Java and Spring",
            salary="$90,000 - $100,000",
            url="https://example.com/job",
            required_skills=["Java", "Spring", "Kafka"]
        )
    ]

    service.process(sample_jobs)


if __name__ == "__main__":
    main()