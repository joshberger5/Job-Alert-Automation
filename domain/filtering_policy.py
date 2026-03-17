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

_GLOBAL_LOCATION_WORDS: frozenset[str] = frozenset({
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


def _location_suggests_remote(location: str) -> bool:
    """True if the location explicitly indicates remote or global availability.

    Requires either the word 'remote' in the location string, or a word that
    unambiguously means global availability (worldwide, global, anywhere).
    This intentionally excludes 'United States' alone — a US city job whose
    location says 'New York, United States' should NOT be treated as remote.
    """
    lower: str = location.lower()
    if re.search(r"\bremote\b", lower):
        return True
    words: set[str] = set(re.sub(r"[^a-zA-Z\s]", " ", lower).split())
    return bool(words & _GLOBAL_LOCATION_WORDS)


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

        # 3. Remote check — location must explicitly suggest remote
        if profile.remote_allowed:
            if job.remote is True and _is_globally_or_us_remote(job.location):
                return True
            if job.remote is None and _location_suggests_remote(job.location) and _is_globally_or_us_remote(job.location):
                return True

        # 4. Location check
        location_text: str = job.location.lower()
        for location in profile.preferred_locations:
            if location.lower() in location_text:
                return True

        return False

    def is_unverified_remote(self, job: Job, profile: CandidateProfile) -> bool:
        """True when the job mentions remote work in its description but the
        location doesn't confirm it — i.e. it didn't pass allows() via remote."""
        if not profile.remote_allowed:
            return False
        if self.allows(job, profile):
            return False
        return _mentions_remote_work(job)
