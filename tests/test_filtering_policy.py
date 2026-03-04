from domain.candidate_profile import CandidateProfile
from domain.filtering_policy import FilteringPolicy
from domain.job import Job


_POLICY: FilteringPolicy = FilteringPolicy()


def _make_profile(
    preferred_locations: list[str] | None = None,
    remote_allowed: bool = True,
    ideal_max_experience_years: int = 3,
    open_to_contract: bool = False,
) -> CandidateProfile:
    return CandidateProfile(
        preferred_locations=preferred_locations if preferred_locations is not None else ["Jacksonville"],
        remote_allowed=remote_allowed,
        ideal_max_experience_years=ideal_max_experience_years,
        core_skills={"java": 4},
        secondary_skills={},
        open_to_contract=open_to_contract,
    )


def _make_job(
    location: str = "Jacksonville, FL",
    description: str = "Java developer role.",
    remote: bool | None = None,
    employment_type: str | None = "full-time",
) -> Job:
    return Job(
        id="test-1",
        title="Software Engineer",
        company="Acme",
        location=location,
        description=description,
        remote=remote,
        employment_type=employment_type,
    )


# ---------------------------------------------------------------------------
# Contract filter
# ---------------------------------------------------------------------------


def test_contract_job_rejected_when_closed_to_contract() -> None:
    job: Job = _make_job(employment_type="contract")
    profile: CandidateProfile = _make_profile(open_to_contract=False)
    assert _POLICY.allows(job, profile) is False


def test_contract_job_allowed_when_open_to_contract() -> None:
    job: Job = _make_job(location="Jacksonville, FL", employment_type="contract")
    profile: CandidateProfile = _make_profile(open_to_contract=True)
    assert _POLICY.allows(job, profile) is True


# ---------------------------------------------------------------------------
# Experience gap filter
# ---------------------------------------------------------------------------


def test_moderate_gap_experience_filtered() -> None:
    """4 years required vs ideal_max=3 → MODERATE_GAP → filtered."""
    job: Job = _make_job(description="4 years experience required.", location="Jacksonville, FL")
    profile: CandidateProfile = _make_profile(ideal_max_experience_years=3)
    assert _POLICY.allows(job, profile) is False


def test_large_gap_experience_filtered() -> None:
    """6 years required vs ideal_max=3 → LARGE_GAP → filtered."""
    job: Job = _make_job(description="6 years experience required.", location="Jacksonville, FL")
    profile: CandidateProfile = _make_profile(ideal_max_experience_years=3)
    assert _POLICY.allows(job, profile) is False


def test_within_range_experience_allowed() -> None:
    """3 years required vs ideal_max=3 → WITHIN_IDEAL_RANGE → not filtered."""
    job: Job = _make_job(description="3 years experience required.", location="Jacksonville, FL")
    profile: CandidateProfile = _make_profile(ideal_max_experience_years=3)
    assert _POLICY.allows(job, profile) is True


# ---------------------------------------------------------------------------
# Remote check
# ---------------------------------------------------------------------------


def test_remote_true_us_location_allowed() -> None:
    """remote=True + US location → allowed."""
    job: Job = _make_job(location="Remote, United States", remote=True)
    profile: CandidateProfile = _make_profile(remote_allowed=True)
    assert _POLICY.allows(job, profile) is True


def test_remote_true_purely_remote_allowed() -> None:
    """remote=True + purely "Remote" location → allowed."""
    job: Job = _make_job(location="Remote", remote=True)
    profile: CandidateProfile = _make_profile(remote_allowed=True, preferred_locations=[])
    assert _POLICY.allows(job, profile) is True


def test_remote_true_europe_filtered() -> None:
    """remote=True + Europe-only location → filtered (not US-accessible)."""
    job: Job = _make_job(location="Remote, Europe", remote=True)
    profile: CandidateProfile = _make_profile(remote_allowed=True, preferred_locations=[])
    assert _POLICY.allows(job, profile) is False


def test_remote_none_with_remote_phrase_worldwide_allowed() -> None:
    """remote=None + remote phrase in description + worldwide location → allowed."""
    job: Job = _make_job(
        location="Worldwide",
        description="This is a remote position. Java required.",
        remote=None,
    )
    profile: CandidateProfile = _make_profile(remote_allowed=True, preferred_locations=[])
    assert _POLICY.allows(job, profile) is True


# ---------------------------------------------------------------------------
# Location substring match
# ---------------------------------------------------------------------------


def test_preferred_location_match_allowed() -> None:
    """Location substring match → allowed regardless of remote."""
    job: Job = _make_job(location="Jacksonville, FL", remote=None)
    profile: CandidateProfile = _make_profile(preferred_locations=["Jacksonville"])
    assert _POLICY.allows(job, profile) is True


def test_no_match_location_not_remote_filtered() -> None:
    """No remote, no preferred location → filtered."""
    job: Job = _make_job(location="Seattle, WA", remote=None)
    profile: CandidateProfile = _make_profile(
        preferred_locations=["Jacksonville"],
        remote_allowed=True,
    )
    assert _POLICY.allows(job, profile) is False
