from __future__ import annotations

import re

from domain.candidate_profile import CandidateProfile
from domain.experience_alignment import ExperienceAlignment
from domain.job import Job
from domain.salary_range import SalaryRange


_US_WORDS: frozenset[str] = frozenset({
    "us", "usa", "united", "states", "america",
    "worldwide", "global", "anywhere",
})


def _is_globally_or_us_remote(location: str) -> bool:
    """True if the location indicates a globally or US-accessible remote role."""
    stripped: str = re.sub(r"\bremote\b", "", location, flags=re.IGNORECASE)
    stripped = re.sub(r"[^a-zA-Z\s]", " ", stripped).strip().lower()
    if not stripped:
        return True  # purely "Remote" with nothing else
    words: set[str] = set(stripped.split())
    return bool(words & _US_WORDS)


_REMOTE_WORK_PHRASES: tuple[str, ...] = (
    "fully remote",
    "100% remote",
    "work from home",
    "wfh",
    "remote position",
    "remote role",
    "remote only",
    "remote-only",
    "this is a remote",
    "remote work environment",
)


def _mentions_remote_work(job: Job) -> bool:
    """True only when the job explicitly signals it is a remote role."""
    combined: str = (job.description + " " + job.location).lower()
    return any(phrase in combined for phrase in _REMOTE_WORK_PHRASES)


class FilteringPolicy:

    def allows(self, job: Job, profile: CandidateProfile) -> bool:
        # 1. Contract filter
        if not profile.open_to_contract and job.employment_type == "contract":
            return False

        # 1.5. Salary floor filter
        if profile.minimum_salary > 0:
            salary_range: SalaryRange = job.salary_range()
            if salary_range.maximum is not None and salary_range.maximum < profile.minimum_salary:
                return False

        # 2. Experience gap filter (skip when ideal_max not set)
        if profile.ideal_max_experience_years > 0:
            alignment: ExperienceAlignment = job.experience_requirement().alignment_with(
                profile.ideal_max_experience_years
            )
            if alignment in (ExperienceAlignment.MODERATE_GAP, ExperienceAlignment.LARGE_GAP):
                return False

        # 3. Remote check
        if profile.remote_allowed:
            if job.remote is True and _is_globally_or_us_remote(job.location):
                return True
            if job.remote is None and _mentions_remote_work(job) and _is_globally_or_us_remote(job.location):
                return True

        # 4. Location check
        location_text: str = job.location.lower()
        for location in profile.preferred_locations:
            if location.lower() in location_text:
                return True

        return False
