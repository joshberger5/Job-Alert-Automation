from domain.candidate_profile import CandidateProfile
from domain.job import Job
from domain.scoring_policy import ScoringPolicy


def _make_profile(
    core_skills: dict[str, int] | None = None,
    secondary_skills: dict[str, int] | None = None,
) -> CandidateProfile:
    return CandidateProfile(
        preferred_locations=["Jacksonville"],
        remote_allowed=True,
        ideal_max_experience_years=3,
        core_skills=core_skills if core_skills is not None else {"java": 4},
        secondary_skills=secondary_skills if secondary_skills is not None else {},
        open_to_contract=False,
    )


def _make_job(description: str, required_skills: list[str] | None = None) -> Job:
    return Job(
        id="test-1",
        title="Software Engineer",
        company="Acme",
        location="Jacksonville, FL",
        description=description,
        required_skills=required_skills or [],
    )


policy: ScoringPolicy = ScoringPolicy()


# ---------------------------------------------------------------------------
# Word-boundary matching (validates Step 1 fix)
# ---------------------------------------------------------------------------


def test_java_does_not_match_javascript() -> None:
    """"java" skill must NOT match a description containing only "javascript"."""
    job: Job = _make_job("We use javascript and typescript.")
    profile: CandidateProfile = _make_profile(core_skills={"java": 4})
    score, breakdown = policy.evaluate(job, profile)
    assert "core:java" not in breakdown
    assert score == 0


def test_java_matches_java_developer() -> None:
    """"java" skill SHOULD match a description mentioning "java developer"."""
    job: Job = _make_job("Looking for a senior java developer.")
    profile: CandidateProfile = _make_profile(core_skills={"java": 4})
    score, breakdown = policy.evaluate(job, profile)
    assert "core:java" in breakdown
    assert score == 4


def test_c_does_not_match_account() -> None:
    """Single-letter "c" skill must not match "account", "contract", etc."""
    job: Job = _make_job("Manage customer accounts and contracts.")
    profile: CandidateProfile = _make_profile(core_skills={"c": 4})
    score, breakdown = policy.evaluate(job, profile)
    assert "core:c" not in breakdown
    assert score == 0


def test_c_matches_standalone_c() -> None:
    """Single-letter "c" skill SHOULD match when "c" appears as its own word."""
    job: Job = _make_job("Experience with c and c++ programming.")
    profile: CandidateProfile = _make_profile(core_skills={"c": 4})
    score, _ = policy.evaluate(job, profile)
    assert score == 4


# ---------------------------------------------------------------------------
# Missing-skill penalty
# ---------------------------------------------------------------------------


def test_missing_required_skill_incurs_penalty() -> None:
    """A required skill the candidate lacks should subtract 2 from the score."""
    job: Job = _make_job(
        "Java developer needed.",
        required_skills=["Kubernetes"],
    )
    profile: CandidateProfile = _make_profile(
        core_skills={"java": 4},
        secondary_skills={},
    )
    score, breakdown = policy.evaluate(job, profile)
    assert breakdown.get("missing:kubernetes") == -2
    assert score == 4 + (-2)


def test_present_required_skill_no_penalty() -> None:
    """A required skill the candidate has should not incur a penalty."""
    job: Job = _make_job(
        "Java developer needed.",
        required_skills=["Java"],
    )
    profile: CandidateProfile = _make_profile(core_skills={"java": 4})
    score, breakdown = policy.evaluate(job, profile)
    assert "missing:java" not in breakdown


# ---------------------------------------------------------------------------
# Qualifies threshold
# ---------------------------------------------------------------------------


def test_qualifies_below_minimum_returns_false() -> None:
    assert policy.qualifies(6) is False


def test_qualifies_at_minimum_returns_true() -> None:
    assert policy.qualifies(7) is True


def test_qualifies_above_minimum_returns_true() -> None:
    assert policy.qualifies(10) is True
