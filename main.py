import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from dotenv import load_dotenv

from domain.candidate_profile import CandidateProfile
from domain.filtering_policy import FilteringPolicy
from domain.job import Job
from domain.scoring_policy import ScoringPolicy

from application.job_processing_service import JobProcessingService
from application.resume_profile_builder import ResumeProfileBuilder
from application.simple_event_dispatcher import SimpleEventDispatcher

from infrastructure.json_job_repository import JsonJobRepository
from infrastructure.in_memory_event_publisher import InMemoryEventPublisher
from infrastructure.email_notifier import EmailNotifier
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


def _print_profile(profile: CandidateProfile) -> None:
    core: str = ", ".join(f"{k} ({v})" for k, v in profile.core_skills.items())
    secondary: str = ", ".join(f"{k} ({v})" for k, v in profile.secondary_skills.items())
    rows: list[tuple[str, str]] = [
        ("Locations",  ", ".join(profile.preferred_locations)),
        ("Remote",     "Yes" if profile.remote_allowed else "No"),
        ("Salary Min", f"${profile.salary_minimum:,}"),
        ("Max Exp",    f"{profile.ideal_max_experience_years} years"),
        ("Contract",   "Yes" if profile.open_to_contract else "No"),
        ("Core Skills", core),
        ("Secondary",  secondary),
        ("Prev Titles", ", ".join(profile.previous_titles)),
    ]
    print()
    print("  Candidate Profile")
    print("  " + "─" * 64)
    for label, value in rows:
        print(f"  {label:<13}  {value}")
    print("  " + "─" * 64)
    print()


def _fetcher_label(fetcher: JobFetcher) -> str:
    return getattr(fetcher, "company_name", type(fetcher).__name__)


def _run_fetcher(fetcher: JobFetcher) -> tuple[str, list[Job], Exception | None]:
    label: str = _fetcher_label(fetcher)
    try:
        jobs: list[Job] = fetcher.fetch()
        return label, jobs, None
    except Exception as e:
        return label, [], e


def main() -> None:
    start: float = time.monotonic()
    run_at: datetime = datetime.now()

    parser = PdfResumeParser()
    resume_text: str = parser.extract_text("resume.pdf")

    builder = ResumeProfileBuilder()
    profile: CandidateProfile = builder.build(resume_text)
    _print_profile(profile)

    repository = JsonJobRepository()
    filtering_policy = FilteringPolicy()
    scoring_policy = ScoringPolicy()

    dispatcher = SimpleEventDispatcher()
    publisher = InMemoryEventPublisher(dispatcher)

    service = JobProcessingService(
        repository=repository,
        scoring_policy=scoring_policy,
        filtering_policy=filtering_policy,
        profile=profile,
        event_publisher=publisher,
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
            company_name="Mayo Clinic (Tampa)",
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

    print(f"  Fetching from {len(fetchers)} sources in parallel...")
    all_jobs: list[Job] = []
    with ThreadPoolExecutor(max_workers=len(fetchers)) as pool:
        futures = {pool.submit(_run_fetcher, f): f for f in fetchers}
        for future in as_completed(futures):
            label, jobs, error = future.result()
            if error:
                print(f"  [{label}] ERROR: {error}")
            else:
                print(f"  [{label}] {len(jobs)} jobs")
            all_jobs.extend(jobs)

    print()
    debug_records: list[dict] = service.process(all_jobs)

    qualified: list[dict] = [r for r in debug_records if r.get("result") == "qualified"]
    counts: dict[str, int] = {}
    for r in debug_records:
        result_key: str = r["result"]
        counts[result_key] = counts.get(result_key, 0) + 1

    print(f"  Results: {counts}")

    if qualified:
        print()
        for r in qualified:
            print(f"  *** {r['title']} @ {r['company']} | Score {r['score']} | {r['url']}")

    debug_output: dict = {
        "run_at": run_at.isoformat(timespec="seconds"),
        "total_fetched": len(all_jobs),
        "summary": counts,
        "jobs": debug_records,
    }
    with open("jobs_debug.json", "w", encoding="utf-8") as f:
        json.dump(debug_output, f, indent=2, default=str)

    duration_s: float = time.monotonic() - start

    if os.environ.get("SMTP_HOST"):
        try:
            EmailNotifier().send(qualified, run_at, duration_s, len(all_jobs))
            print("  [Email] Sent")
        except Exception as e:
            print(f"  [Email] ERROR: {e}")

    print(f"\n  Done in {duration_s:.1f}s")


if __name__ == "__main__":
    main()
