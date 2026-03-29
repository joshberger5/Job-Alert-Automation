from application.job_record import JobRecord
from domain.candidate_profile import CandidateProfile
from infrastructure.keyword_title_filter import KeywordTitleFilter


def _make_profile() -> CandidateProfile:
    return CandidateProfile(
        preferred_locations=["Jacksonville"],
        remote_allowed=True,
        ideal_max_experience_years=3,
        core_skills={"java": 4},
        secondary_skills={},
        open_to_contract=False,
    )


def _make_record(job_id: str, title: str) -> JobRecord:
    return JobRecord(
        id=job_id,
        title=title,
        company="Acme",
        location="Remote",
        result="qualified",
    )


_PROFILE: CandidateProfile = _make_profile()


# ---------------------------------------------------------------------------
# Rejection
# ---------------------------------------------------------------------------


def test_data_scientist_rejected() -> None:
    kf: KeywordTitleFilter = KeywordTitleFilter()
    records: list[JobRecord] = [_make_record("1", "Data Scientist")]
    approved: set[str] = kf.filter_by_title(records, _PROFILE)
    assert "1" not in approved


def test_product_manager_rejected() -> None:
    kf: KeywordTitleFilter = KeywordTitleFilter()
    records: list[JobRecord] = [_make_record("1", "Senior Product Manager")]
    approved: set[str] = kf.filter_by_title(records, _PROFILE)
    assert "1" not in approved


def test_rejection_is_case_insensitive() -> None:
    kf: KeywordTitleFilter = KeywordTitleFilter()
    records: list[JobRecord] = [_make_record("1", "PRODUCT MANAGER")]
    approved: set[str] = kf.filter_by_title(records, _PROFILE)
    assert "1" not in approved


# ---------------------------------------------------------------------------
# Approval
# ---------------------------------------------------------------------------


def test_java_backend_engineer_approved() -> None:
    kf: KeywordTitleFilter = KeywordTitleFilter()
    records: list[JobRecord] = [_make_record("1", "Java Backend Engineer")]
    approved: set[str] = kf.filter_by_title(records, _PROFILE)
    assert "1" in approved


def test_software_engineer_approved() -> None:
    kf: KeywordTitleFilter = KeywordTitleFilter()
    records: list[JobRecord] = [_make_record("1", "Software Engineer II")]
    approved: set[str] = kf.filter_by_title(records, _PROFILE)
    assert "1" in approved


# ---------------------------------------------------------------------------
# Custom rejected_fragments
# ---------------------------------------------------------------------------


def test_data_analyst_rejected() -> None:
    kf: KeywordTitleFilter = KeywordTitleFilter()
    records: list[JobRecord] = [_make_record("1", "Risk Strategy Data Analyst")]
    approved: set[str] = kf.filter_by_title(records, _PROFILE)
    assert "1" not in approved


def test_site_reliability_engineer_rejected() -> None:
    kf: KeywordTitleFilter = KeywordTitleFilter()
    records: list[JobRecord] = [_make_record("1", "Senior Site Reliability Engineer, Identity Platform")]
    approved: set[str] = kf.filter_by_title(records, _PROFILE)
    assert "1" not in approved


def test_solutions_engineer_rejected() -> None:
    kf: KeywordTitleFilter = KeywordTitleFilter()
    records: list[JobRecord] = [_make_record("1", "Senior Technical Solutions Engineer")]
    approved: set[str] = kf.filter_by_title(records, _PROFILE)
    assert "1" not in approved


def test_test_infrastructure_rejected() -> None:
    kf: KeywordTitleFilter = KeywordTitleFilter()
    records: list[JobRecord] = [_make_record("1", "Senior Software Engineer - Consumer Engineering Test Infrastructure")]
    approved: set[str] = kf.filter_by_title(records, _PROFILE)
    assert "1" not in approved


def test_application_security_rejected() -> None:
    kf: KeywordTitleFilter = KeywordTitleFilter()
    records: list[JobRecord] = [_make_record("1", "Senior Engineer, Application Security")]
    approved: set[str] = kf.filter_by_title(records, _PROFILE)
    assert "1" not in approved


def test_security_engineer_rejected() -> None:
    kf: KeywordTitleFilter = KeywordTitleFilter()
    records: list[JobRecord] = [_make_record("1", "Security Engineer II Canada")]
    approved: set[str] = kf.filter_by_title(records, _PROFILE)
    assert "1" not in approved


def test_business_analyst_rejected() -> None:
    kf: KeywordTitleFilter = KeywordTitleFilter()
    records: list[JobRecord] = [_make_record("1", "Business Analyst - Project Lead")]
    approved: set[str] = kf.filter_by_title(records, _PROFILE)
    assert "1" not in approved


def test_staff_software_engineer_rejected() -> None:
    kf: KeywordTitleFilter = KeywordTitleFilter()
    records: list[JobRecord] = [_make_record("1", "Staff Software Engineer, Backend - Platform (FinHub - Ledger)")]
    approved: set[str] = kf.filter_by_title(records, _PROFILE)
    assert "1" not in approved


# ---------------------------------------------------------------------------
# Whitelist (overrides reject list)
# ---------------------------------------------------------------------------


def test_backend_software_engineer_whitelisted() -> None:
    kf: KeywordTitleFilter = KeywordTitleFilter()
    records: list[JobRecord] = [_make_record("1", "Senior Software Engineer, Backend - Platform (FinHub - Ledger)")]
    approved: set[str] = kf.filter_by_title(records, _PROFILE)
    assert "1" in approved


def test_whitelist_overrides_role_type_reject() -> None:
    """A whitelisted title must be approved even if it also matches a role-type reject fragment."""
    kf: KeywordTitleFilter = KeywordTitleFilter()
    # Contains "software engineer, backend" (whitelist) AND "test infrastructure" (role-type reject)
    records: list[JobRecord] = [_make_record("1", "Software Engineer, Backend — Test Infrastructure")]
    approved: set[str] = kf.filter_by_title(records, _PROFILE)
    assert "1" in approved


def test_whitelist_does_not_override_hard_reject() -> None:
    """A whitelisted title must still be rejected if it matches a hard (seniority) reject fragment."""
    kf: KeywordTitleFilter = KeywordTitleFilter()
    # Contains "software engineer, backend" (whitelist) AND "staff software" (hard reject)
    records: list[JobRecord] = [_make_record("1", "Staff Software Engineer, Backend - Platform")]
    approved: set[str] = kf.filter_by_title(records, _PROFILE)
    assert "1" not in approved


def test_custom_fragments_override_defaults() -> None:
    kf: KeywordTitleFilter = KeywordTitleFilter(rejected_fragments=["wizard"])
    records: list[JobRecord] = [
        _make_record("1", "Data Scientist"),   # default fragment — NOT rejected with custom list
        _make_record("2", "Code Wizard"),       # custom fragment — rejected
    ]
    approved: set[str] = kf.filter_by_title(records, _PROFILE)
    assert "1" in approved
    assert "2" not in approved
