import json
import os
from datetime import datetime
from dotenv import load_dotenv

from domain.filtering_policy import FilteringPolicy
from domain.scoring_policy import ScoringPolicy
from domain.events import DomainEvent, JobQualified

from application.job_processing_service import JobProcessingService
from application.resume_profile_builder import ResumeProfileBuilder
from application.simple_event_dispatcher import SimpleEventDispatcher

from infrastructure.json_job_repository import JsonJobRepository
from infrastructure.in_memory_event_publisher import InMemoryEventPublisher
from infrastructure.resume.pdf_resume_parser import PdfResumeParser
from infrastructure.job_fetchers import JobFetcher

from infrastructure.job_fetchers.adzuna_fetcher import AdzunaFetcher
from infrastructure.job_fetchers.greenhouse_fetcher import GreenhouseFetcher
from infrastructure.job_fetchers.lever_fetcher import LeverFetcher
from infrastructure.job_fetchers.phenom_fetcher import PhenomFetcher
from infrastructure.job_fetchers.workday_fetcher import WorkdayFetcher
from infrastructure.job_fetchers.boa_fetcher import BankOfAmericaFetcher
from infrastructure.job_fetchers.icims_fetcher import IcimsFetcher, IcimsSitemapFetcher

load_dotenv()


def job_qualified_handler(event: DomainEvent) -> None:
    assert isinstance(event, JobQualified)
    print(f"\n*** JOB QUALIFIED: {event.url} | Score: {event.score}")


def main() -> None:

    parser = PdfResumeParser()
    resume_text = parser.extract_text("resume.pdf")

    builder = ResumeProfileBuilder()
    profile = builder.build(resume_text)

    print(profile)

    repository = JsonJobRepository()
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

    fetchers: list[JobFetcher] = [
        AdzunaFetcher(
            app_id=os.environ["ADZUNA_APP_ID"],
            app_key=os.environ["ADZUNA_APP_KEY"],
        ),
        GreenhouseFetcher(company="sofi", company_name="SoFi"),
        LeverFetcher(
            company="dnb",
            company_name="Dun & Bradstreet",
            location="Jacksonville - Florida - United States",
        ),
        PhenomFetcher(base_domain="jobs.citi.com", org_id="287", company_name="Citi"),
        PhenomFetcher(
            base_domain="jobs.mayoclinic.org",
            org_id="33647",
            company_name="Mayo Clinic",
        ),
        PhenomFetcher(
            base_domain="jobs.mayoclinic.org",
            org_id="33647",
            company_name="Mayo Clinic",
            latitude=27.9506,
            longitude=-82.4572,
        ),
        PhenomFetcher(base_domain="jobs.us.pwc.com", org_id="932", company_name="PwC"),
        WorkdayFetcher(
            base_url="https://wd1.myworkdaysite.com",
            tenant="ssctech",
            company="SSCTechnologies",
            company_name="SSC Technologies",
            recruiting_base="https://wd1.myworkdaysite.com/recruiting/ssctech/SSCTechnologies",
            fetch_descriptions=True,
            location_ids=["b5aa81dc192f01dee656c4c5ce2312b9"],
        ),
        WorkdayFetcher(
            base_url="https://vystarcu.wd1.myworkdayjobs.com",
            tenant="vystarcu",
            company="Careers",
            company_name="VyStar Credit Union",
            recruiting_base="https://vystarcu.wd1.myworkdayjobs.com/Careers",
            search_text="",
            fetch_descriptions=True,
            location_ids=["9c1a239b35bd4598856e5393b249b8a1"],
        ),
        BankOfAmericaFetcher(location="Jacksonville, FL"),
        BankOfAmericaFetcher(location="Jacksonville, FL", keywords="Java"),
        IcimsFetcher(base_url="https://jobs.paysafe.com", company_name="Paysafe"),
        IcimsSitemapFetcher(
            base_url="https://careers-fnf.icims.com",
            company_name="FNF",
            location_filter=None,
        ),
    ]

    all_jobs = []
    for fetcher in fetchers:
        fetcher_name = type(fetcher).__name__
        try:
            jobs = fetcher.fetch()
            print(f"[{fetcher_name}] Fetched {len(jobs)} jobs")
            all_jobs.extend(jobs)
        except Exception as e:
            print(f"[{fetcher_name}] ERROR: {e}")

    debug_records = service.process(all_jobs)

    counts: dict[str, int] = {}
    for r in debug_records:
        counts[r["result"]] = counts.get(r["result"], 0) + 1
    print(f"[Processing] {counts}")

    debug_output = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "total_fetched": len(all_jobs),
        "summary": counts,
        "jobs": debug_records,
    }
    with open("jobs_debug.json", "w", encoding="utf-8") as f:
        json.dump(debug_output, f, indent=2, default=str)
    print("[Debug] Wrote jobs_debug.json")


if __name__ == "__main__":
    main()
