import re
from dataclasses import dataclass
from domain.experience_alignment import ExperienceAlignment


@dataclass(frozen=True)
class ExperienceRequirement:
    required_years: int | None

    _YEAR_TOKENS: frozenset[str] = frozenset({"year", "years", "yrs"})
    _EXPERIENCE_CONTEXT: frozenset[str] = frozenset({"experience", "experiences", "experienced", "exp"})
    _CONTEXT_WINDOW: int = 8
    _MAX_YEARS: int = 20

    @staticmethod
    def from_job_content(job_content: str) -> "ExperienceRequirement":
        tokens: list[str] = job_content.lower().split()

        for index, token in enumerate(tokens):
            # Accept "15", "15+", "5-10" — extract the leading digit sequence
            m: re.Match[str] | None = re.match(r'^(\d+)', token)
            if not m:
                continue
            years: int = int(m.group(1))
            if years > ExperienceRequirement._MAX_YEARS:
                continue
            if index + 1 >= len(tokens):
                continue
            # Strip punctuation so "years," "years'" "years." all match
            next_token: str = re.sub(r"[^a-z]", "", tokens[index + 1])
            if next_token not in ExperienceRequirement._YEAR_TOKENS:
                continue
            window_start: int = max(0, index - ExperienceRequirement._CONTEXT_WINDOW)
            window_end: int = min(len(tokens), index + ExperienceRequirement._CONTEXT_WINDOW + 2)
            window: list[str] = tokens[window_start:window_end]
            if any(w in ExperienceRequirement._EXPERIENCE_CONTEXT for w in window):
                return ExperienceRequirement(years)

        return ExperienceRequirement(None)

    def alignment_with(
        self,
        ideal_max_years: int
    ) -> ExperienceAlignment:

        if self.required_years is None:
            return ExperienceAlignment.UNKNOWN

        if self.required_years <= ideal_max_years:
            return ExperienceAlignment.WITHIN_IDEAL_RANGE

        if self.required_years <= ideal_max_years + 4:
            return ExperienceAlignment.MODERATE_GAP

        return ExperienceAlignment.LARGE_GAP