from unittest.mock import MagicMock

from application.event_publisher import EventPublisher
from application.feedback_bias_service import FeedbackBiasService
from application.job_processing_service import JobProcessingService
from application.job_record import JobRecord
from application.job_repository import JobRepository
from domain.candidate_profile import CandidateProfile
from domain.events import DomainEvent, JobEvaluated, JobQualified
from domain.filtering_policy import FilteringPolicy
from domain.job import Job
from domain.scoring_policy import ScoringPolicy


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_job(
    job_id: str = "job-1",
    title: str = "Java Developer",
    company: str = "Acme Corp",
    location: str = "Jacksonville, FL",
    description: str = "We need a Java developer.",
    employment_type: str | None = "full-time",
    remote: bool | None = None,
    required_skills: list[str] | None = None,
) -> Job:
    return Job(
        id=job_id,
        title=title,
        company=company,
        location=location,
        description=description,
        salary="$90,000 - $120,000",
        url=f"https://example.com/jobs/{job_id}",
        required_skills=required_skills or [],
        remote=remote,
        employment_type=employment_type,
    )


def _make_profile() -> CandidateProfile:
    return CandidateProfile(
        preferred_locations=["Jacksonville"],
        remote_allowed=True,
        ideal_max_experience_years=3,
        core_skills={"java": 4},
        secondary_skills={"python": 2},
        open_to_contract=False,
    )


def _make_repo(exists: bool = False) -> MagicMock:
    repo: MagicMock = MagicMock()
    repo.exists.return_value = exists
    return repo


def _make_filtering(allows: bool = True) -> MagicMock:
    policy: MagicMock = MagicMock()
    policy.allows.return_value = allows
    return policy


def _make_scoring(score: int = 10) -> MagicMock:
    policy: MagicMock = MagicMock()
    policy.evaluate.return_value = (score, {"core:java": score})
    policy.qualifies.side_effect = lambda s: s >= ScoringPolicy.MINIMUM_SCORE
    return policy


def _make_publisher() -> MagicMock:
    return MagicMock()


def _build_service(
    repo: MagicMock | None = None,
    filtering: MagicMock | None = None,
    scoring: MagicMock | None = None,
    publisher: MagicMock | None = None,
) -> tuple[JobProcessingService, MagicMock, MagicMock, MagicMock, MagicMock]:
    r: MagicMock = repo or _make_repo()
    f: MagicMock = filtering or _make_filtering()
    s: MagicMock = scoring or _make_scoring()
    p: MagicMock = publisher or _make_publisher()
    svc: JobProcessingService = JobProcessingService(
        repository=r,
        scoring_policy=s,
        filtering_policy=f,
        profile=_make_profile(),
        event_publisher=p,
    )
    return svc, r, f, s, p


def _published_events(publisher: MagicMock) -> list[DomainEvent]:
    return list(publisher.publish.call_args.args[0])


# ---------------------------------------------------------------------------
# Duplicate path
# ---------------------------------------------------------------------------


def test_duplicate_result() -> None:
    svc, repo, _, _, _ = _build_service(repo=_make_repo(exists=True))
    records: list[JobRecord] = svc.process([_make_job()])

    assert records[0]["result"] == "duplicate"


def test_duplicate_skips_save() -> None:
    svc, repo, _, _, _ = _build_service(repo=_make_repo(exists=True))
    svc.process([_make_job()])

    repo.save.assert_not_called()


def test_duplicate_emits_no_events() -> None:
    svc, _, _, _, publisher = _build_service(repo=_make_repo(exists=True))
    svc.process([_make_job()])

    assert _published_events(publisher) == []


# ---------------------------------------------------------------------------
# Filtered-out path
# ---------------------------------------------------------------------------


def test_filtered_out_result() -> None:
    svc, _, _, _, _ = _build_service(filtering=_make_filtering(allows=False))
    records: list[JobRecord] = svc.process([_make_job()])

    assert records[0]["result"] == "filtered_out"


def test_filtered_out_has_filter_reason() -> None:
    svc, _, _, _, _ = _build_service(filtering=_make_filtering(allows=False))
    records: list[JobRecord] = svc.process([_make_job()])

    assert "filter_reason" in records[0]
    assert isinstance(records[0]["filter_reason"], str)
    assert len(records[0]["filter_reason"]) > 0


def test_filtered_out_saves_with_zero_score() -> None:
    repo: MagicMock = _make_repo()
    svc, _, _, _, _ = _build_service(
        repo=repo, filtering=_make_filtering(allows=False)
    )
    job: Job = _make_job()
    svc.process([job])

    repo.save.assert_called_once_with(job, 0, False)


def test_filtered_out_emits_no_events() -> None:
    svc, _, _, _, publisher = _build_service(filtering=_make_filtering(allows=False))
    svc.process([_make_job()])

    assert _published_events(publisher) == []


# ---------------------------------------------------------------------------
# Qualified path
# ---------------------------------------------------------------------------


def test_qualified_result() -> None:
    svc, _, _, _, _ = _build_service(scoring=_make_scoring(score=10))
    records: list[JobRecord] = svc.process([_make_job()])

    assert records[0]["result"] == "qualified"
    assert records[0]["qualified"] is True


def test_qualified_record_has_score_and_breakdown() -> None:
    svc, _, _, _, _ = _build_service(scoring=_make_scoring(score=10))
    records: list[JobRecord] = svc.process([_make_job()])

    assert records[0]["score"] == 10
    assert isinstance(records[0]["score_breakdown"], dict)


def test_qualified_saves_with_correct_args() -> None:
    repo: MagicMock = _make_repo()
    svc, _, _, _, _ = _build_service(repo=repo, scoring=_make_scoring(score=10))
    job: Job = _make_job()
    svc.process([job])

    repo.save.assert_called_once_with(job, 10, True)


def test_qualified_emits_evaluated_and_qualified_events() -> None:
    svc, _, _, _, publisher = _build_service(scoring=_make_scoring(score=10))
    job: Job = _make_job()
    svc.process([job])

    events: list[DomainEvent] = _published_events(publisher)
    evaluated: list[JobEvaluated] = [e for e in events if isinstance(e, JobEvaluated)]
    qualified_events: list[JobQualified] = [e for e in events if isinstance(e, JobQualified)]

    assert len(evaluated) == 1
    assert evaluated[0].job_id == job.id
    assert evaluated[0].score == 10
    assert evaluated[0].qualified is True

    assert len(qualified_events) == 1
    assert qualified_events[0].job_id == job.id
    assert qualified_events[0].score == 10
    assert qualified_events[0].url == job.url


# ---------------------------------------------------------------------------
# Scored-out path
# ---------------------------------------------------------------------------


def test_scored_out_result() -> None:
    svc, _, _, _, _ = _build_service(scoring=_make_scoring(score=3))
    records: list[JobRecord] = svc.process([_make_job()])

    assert records[0]["result"] == "scored_out"
    assert records[0]["qualified"] is False


def test_scored_out_saves_with_correct_args() -> None:
    repo: MagicMock = _make_repo()
    svc, _, _, _, _ = _build_service(repo=repo, scoring=_make_scoring(score=3))
    job: Job = _make_job()
    svc.process([job])

    repo.save.assert_called_once_with(job, 3, False)


def test_scored_out_emits_only_evaluated_event() -> None:
    svc, _, _, _, publisher = _build_service(scoring=_make_scoring(score=3))
    job: Job = _make_job()
    svc.process([job])

    events: list[DomainEvent] = _published_events(publisher)
    assert len(events) == 1
    assert isinstance(events[0], JobEvaluated)
    assert events[0].qualified is False


# ---------------------------------------------------------------------------
# Record base fields
# ---------------------------------------------------------------------------


def test_record_contains_all_base_fields() -> None:
    svc, _, _, _, _ = _build_service()
    job: Job = _make_job(
        job_id="abc",
        title="Engineer",
        company="Corp",
        location="Jacksonville, FL",
        description="desc text",
        employment_type="full-time",
        remote=None,
    )
    records: list[JobRecord] = svc.process([job])
    r: JobRecord = records[0]

    assert r["id"] == "abc"
    assert r["title"] == "Engineer"
    assert r["company"] == "Corp"
    assert r["location"] == "Jacksonville, FL"
    assert r["remote"] is None
    assert r["employment_type"] == "full-time"
    assert r["salary"] == "$90,000 - $120,000"
    assert r["url"] == "https://example.com/jobs/abc"
    assert r["description_length"] == len("desc text")


# ---------------------------------------------------------------------------
# Mixed batch
# ---------------------------------------------------------------------------


def test_mixed_batch_returns_record_per_job() -> None:
    # Four jobs: duplicate, filtered, qualified, scored_out
    repo: MagicMock = MagicMock()
    repo.exists.side_effect = lambda job_id: job_id == "dup"

    filtering: MagicMock = MagicMock()
    filtering.allows.side_effect = lambda job, profile: job.id != "filtered"

    scoring: MagicMock = MagicMock()
    scoring.evaluate.side_effect = lambda job, profile: (
        (10, {"core:java": 10}) if job.id == "qualified" else (2, {})
    )
    scoring.qualifies.side_effect = lambda s: s >= ScoringPolicy.MINIMUM_SCORE

    svc: JobProcessingService = JobProcessingService(
        repository=repo,
        scoring_policy=scoring,
        filtering_policy=filtering,
        profile=_make_profile(),
        event_publisher=_make_publisher(),
    )

    jobs: list[Job] = [
        _make_job(job_id="dup"),
        _make_job(job_id="filtered"),
        _make_job(job_id="qualified"),
        _make_job(job_id="scored"),
    ]
    records: list[JobRecord] = svc.process(jobs)

    assert len(records) == 4
    results: list[str] = [r["result"] for r in records]
    assert results[0] == "duplicate"
    assert results[1] == "filtered_out"
    assert results[2] == "qualified"
    assert results[3] == "scored_out"


# ---------------------------------------------------------------------------
# FeedbackBiasService integration
# ---------------------------------------------------------------------------


def test_scored_record_has_feedback_multiplier() -> None:
    """A scored (non-duplicate, non-filtered) record must carry a feedback_multiplier float."""
    # Use a no-op FeedbackBiasService (no feedback.json) — multiplier will be 1.0
    bias_svc: FeedbackBiasService = FeedbackBiasService()
    r: MagicMock = _make_repo()
    f: MagicMock = _make_filtering()
    s: MagicMock = _make_scoring(score=10)
    p: MagicMock = _make_publisher()
    svc: JobProcessingService = JobProcessingService(
        repository=r,
        scoring_policy=s,
        filtering_policy=f,
        profile=_make_profile(),
        event_publisher=p,
        feedback_bias_service=bias_svc,
    )

    records: list[JobRecord] = svc.process([_make_job()])

    assert "feedback_multiplier" in records[0]
    assert isinstance(records[0]["feedback_multiplier"], float)
    assert records[0]["feedback_multiplier"] == 1.0
