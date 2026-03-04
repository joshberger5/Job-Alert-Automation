from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class CandidateProfile:
    preferred_locations: List[str]
    remote_allowed: bool

    ideal_max_experience_years: int

    core_skills: Dict[str, int]
    secondary_skills: Dict[str, int]

    open_to_contract: bool = False