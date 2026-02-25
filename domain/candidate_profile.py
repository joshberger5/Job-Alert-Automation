from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class CandidateProfile:
    preferred_locations: List[str]
    remote_allowed: bool

    salary_minimum: int
    ideal_max_experience_years: int

    core_skills: Dict[str, int]
    secondary_skills: Dict[str, int]

    previous_titles: List[str]