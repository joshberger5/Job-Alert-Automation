from dataclasses import dataclass
from domain.experience_alignment import ExperienceAlignment


@dataclass(frozen=True)
class ExperienceRequirement:
    required_years: int | None

    @staticmethod
    def from_job_content(job_content: str) -> "ExperienceRequirement":
        tokens = job_content.lower().split()

        for index, token in enumerate(tokens):
            if token.isdigit():
                if index + 1 < len(tokens):
                    next_token = tokens[index + 1]
                    if next_token in ("year", "years", "yrs"):
                        return ExperienceRequirement(int(token))

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