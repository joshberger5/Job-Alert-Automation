from dataclasses import dataclass
from domain.experience_alignment import ExperienceAlignment


@dataclass(frozen=True)
class ExperienceRequirement:
    required_years: int | None

    _YEAR_TOKENS: frozenset[str] = frozenset({"year", "years", "yrs"})
    _EXPERIENCE_CONTEXT: frozenset[str] = frozenset({"experience", "experiences", "experienced", "exp"})
    _CONTEXT_WINDOW: int = 5
    _MAX_YEARS: int = 20

    @staticmethod
    def from_job_content(job_content: str) -> "ExperienceRequirement":
        tokens: list[str] = job_content.lower().split()

        for index, token in enumerate(tokens):
            digit_str: str = token.rstrip("+")
            if not digit_str.isdigit():
                continue
            years: int = int(digit_str)
            if years > ExperienceRequirement._MAX_YEARS:
                continue
            if index + 1 >= len(tokens):
                continue
            next_token: str = tokens[index + 1]
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

        if self.required_years <= ideal_max_years + 2:
            return ExperienceAlignment.MODERATE_GAP

        return ExperienceAlignment.LARGE_GAP