import contextlib
import io
import json
import os
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import IO

from dotenv import load_dotenv

from application.fetcher_result import FetcherFailure

from domain.candidate_profile import CandidateProfile
from domain.filtering_policy import FilteringPolicy
from domain.job import Job
from domain.scoring_policy import ScoringPolicy

from application.feedback_bias_service import FeedbackBiasService
from application.job_processing_service import JobProcessingService
from application.job_record import JobRecord
from application.resume_profile_builder import ResumeProfileBuilder
from application.simple_event_dispatcher import SimpleEventDispatcher
from application.title_filter_service import TitleFilterService

from infrastructure.json_job_repository import JsonJobRepository
from infrastructure.in_memory_event_publisher import InMemoryEventPublisher
from infrastructure.email_notifier import EmailNotifier, archive_email, build_email_html
from infrastructure.resume.latex_resume_parser import LatexResumeParser
from infrastructure.job_fetchers import JobFetcher
from infrastructure.fetcher_registry import build_fetchers
from infrastructure.keyword_title_filter import KeywordTitleFilter
from infrastructure.llm_title_filter import GeminiTitleFilter

load_dotenv()

_FETCHER_TIMEOUT: int = 120  # seconds per fetcher before giving up


class _Tee:
    """Writes to both the real stdout and a StringIO buffer simultaneously."""

    def __init__(self, primary: IO[str], secondary: io.StringIO) -> None:
        self._primary = primary
        self._secondary = secondary

    def write(self, data: str) -> int:
        self._primary.write(data)
        return self._secondary.write(data)

    def flush(self) -> None:
        self._primary.flush()
        self._secondary.flush()


def _print_profile(profile: CandidateProfile) -> None:
    core: str = ", ".join(f"{k} ({v})" for k, v in profile.core_skills.items())
    secondary: str = ", ".join(f"{k} ({v})" for k, v in profile.secondary_skills.items())
    rows: list[tuple[str, str]] = [
        ("Locations",  ", ".join(profile.preferred_locations)),
        ("Remote",     "Yes" if profile.remote_allowed else "No"),
        ("Max Exp",    f"{profile.ideal_max_experience_years} years"),
        ("Contract",   "Yes" if profile.open_to_contract else "No"),
        ("Core Skills", core),
        ("Secondary",  secondary),
    ]
    print()
    print("  Candidate Profile")
    print("  " + "─" * 64)
    for label, value in rows:
        print(f"  {label:<13}  {value}")
    print("  " + "─" * 64)
    print()


def _fetcher_label(fetcher: JobFetcher) -> str:
    return fetcher.company_name


def _run_fetcher(fetcher: JobFetcher) -> tuple[str, list[Job], FetcherFailure | None]:
    label: str = _fetcher_label(fetcher)
    last_error: Exception | None = None
    for _attempt in range(1, 3):  # attempts 1 and 2
        try:
            jobs: list[Job] = fetcher.fetch()
            return label, jobs, None
        except Exception as e:
            last_error = e
    failure: FetcherFailure = {
        "company": label,
        "error": str(last_error),
        "attempts": 2,
    }
    return label, [], failure


def _build_profile() -> CandidateProfile:
    parser: LatexResumeParser = LatexResumeParser()
    resume_text: str = parser.extract_text("resume.tex")
    builder: ResumeProfileBuilder = ResumeProfileBuilder()
    return builder.build(resume_text)


def _build_services(
    profile: CandidateProfile,
) -> tuple[JobProcessingService, JsonJobRepository]:
    repository: JsonJobRepository = JsonJobRepository()
    filtering_policy: FilteringPolicy = FilteringPolicy()
    scoring_policy: ScoringPolicy = ScoringPolicy()
    dispatcher: SimpleEventDispatcher = SimpleEventDispatcher()
    publisher: InMemoryEventPublisher = InMemoryEventPublisher(dispatcher)
    service: JobProcessingService = JobProcessingService(
        repository=repository,
        scoring_policy=scoring_policy,
        filtering_policy=filtering_policy,
        profile=profile,
        event_publisher=publisher,
        feedback_bias_service=FeedbackBiasService(),
    )
    return service, repository


def _fetch_jobs(
    fetchers: list[JobFetcher], timeout: int
) -> tuple[list[Job], list[FetcherFailure], list[str]]:
    all_jobs: list[Job] = []
    failures: list[FetcherFailure] = []
    warnings: list[str] = []
    _FetcherResult = tuple[str, list[Job], FetcherFailure | None]
    with ThreadPoolExecutor(max_workers=max(len(fetchers), 1)) as pool:
        futures: dict[Future[_FetcherResult], JobFetcher] = {
            pool.submit(_run_fetcher, f): f for f in fetchers
        }
        for future in as_completed(futures):
            try:
                label: str
                jobs: list[Job]
                failure: FetcherFailure | None
                label, jobs, failure = future.result(timeout=timeout)
            except TimeoutError:
                label = _fetcher_label(futures[future])
                failures.append({"company": label, "error": "TIMEOUT", "attempts": 1})
                continue
            if failure is not None:
                failures.append(failure)
            else:
                print(f"  [{label}] {len(jobs)} jobs")
                all_jobs.extend(jobs)
    return all_jobs, failures, warnings


def _apply_filters(
    records: list[JobRecord],
    profile: CandidateProfile,
) -> tuple[list[JobRecord], list[JobRecord], list[JobRecord], list[JobRecord], dict[str, int]]:
    gemini_key: str | None = os.environ.get("GEMINI_API_KEY")
    llm_filter: GeminiTitleFilter | None = GeminiTitleFilter(api_key=gemini_key) if gemini_key else None
    filter_svc: TitleFilterService = TitleFilterService(KeywordTitleFilter(), llm_filter)
    filtered: list[JobRecord] = filter_svc.apply(records, profile)

    qualified: list[JobRecord] = [r for r in filtered if r.get("result") == "qualified"]
    llm_filtered: list[JobRecord] = [r for r in filtered if r.get("result") == "llm_filtered"]
    llm_relevant: list[JobRecord] = [r for r in filtered if r.get("llm_relevant")]
    unverified_remote: list[JobRecord] = [r for r in records if r.get("result") == "unverified_remote"]
    counts: dict[str, int] = {}
    for r in records:
        result_key: str = r["result"]
        counts[result_key] = counts.get(result_key, 0) + 1

    return qualified, llm_filtered, llm_relevant, unverified_remote, counts


def _write_debug_json(
    records: list[JobRecord],
    run_at: datetime,
    total_fetched: int,
    counts: dict[str, int],
) -> None:
    debug_output: dict[str, object] = {
        "run_at": run_at.isoformat(timespec="seconds"),
        "total_fetched": total_fetched,
        "summary": counts,
        "jobs": records,
    }
    with open("jobs_debug.json", "w", encoding="utf-8") as f:
        json.dump(debug_output, f, indent=2, default=str)


def _send_email_notification(
    qualified: list[JobRecord],
    run_at: datetime,
    duration_s: float,
    total_fetched: int,
    llm_relevant: list[JobRecord],
    llm_filtered: list[JobRecord],
    unverified_remote: list[JobRecord],
    run_log: str,
) -> None:
    html: str = build_email_html(
        qualified, run_at, duration_s, total_fetched,
        llm_relevant_jobs=llm_relevant or None,
        llm_filtered_jobs=llm_filtered or None,
        unverified_remote_jobs=unverified_remote or None,
        run_log=run_log,
    )
    pat: str = os.environ.get("FEEDBACK_PAT", "")
    archive_email(html, run_at, redact_tokens=[pat] if pat else None)
    if not os.environ.get("SMTP_HOST"):
        return
    try:
        EmailNotifier().send(
            qualified, run_at, duration_s, total_fetched,
            llm_relevant_jobs=llm_relevant or None,
            llm_filtered_jobs=llm_filtered or None,
            unverified_remote_jobs=unverified_remote or None,
            run_log=run_log,
        )
        print("  [Email] Sent")
    except Exception as e:
        print(f"  [Email] ERROR: {e}")


def main() -> None:
    buf: io.StringIO = io.StringIO()
    with contextlib.redirect_stdout(_Tee(sys.stdout, buf)):
        start: float = time.monotonic()
        run_at: datetime = datetime.now()

        profile: CandidateProfile = _build_profile()
        _print_profile(profile)

        service, repository = _build_services(profile)
        fetchers: list[JobFetcher]
        pre_warnings: list[str]
        fetchers, pre_warnings = build_fetchers()
        print(f"  Fetching from {len(fetchers)} sources in parallel...")
        all_jobs: list[Job]
        fetch_failures: list[FetcherFailure]
        fetch_warnings: list[str]
        all_jobs, fetch_failures, fetch_warnings = _fetch_jobs(fetchers, timeout=_FETCHER_TIMEOUT)
        warnings: list[str] = pre_warnings + fetch_warnings
        for fail in fetch_failures:
            print(f"  [{fail['company']}] FAILED: {fail.get('error', 'unknown')} (attempts: {fail.get('attempts', '?')})")
        for warning in warnings:
            print(f"  [WARNING] {warning}")

        print()
        records: list[JobRecord] = service.process(all_jobs)
        qualified, llm_filtered, llm_relevant, unverified_remote, counts = _apply_filters(records, profile)

        print(f"  Results: {counts}")
        if llm_relevant:
            print(f"  LLM-relevant (scored_out): {len(llm_relevant)}")

        if qualified:
            print()
            for r in qualified:
                print(f"  *** {r['title']} @ {r['company']} | Score {r['score']} | {r['url']}")

        repository.flush()
        _write_debug_json(records, run_at, len(all_jobs), counts)

        duration_s: float = time.monotonic() - start
        print(f"\n  Done in {duration_s:.1f}s")

    run_log: str = buf.getvalue()
    _send_email_notification(qualified, run_at, duration_s, len(all_jobs), llm_relevant, llm_filtered, unverified_remote, run_log)


if __name__ == "__main__":
    main()
