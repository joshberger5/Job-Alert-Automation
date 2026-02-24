from domain.specification import Specification
from domain.experience_alignment import ExperienceAlignment


class ExperienceWithinIdealRangeSpecification(Specification):

    def __init__(self, ideal_max_years: int):
        self.ideal_max_years = ideal_max_years

    def is_satisfied_by(self, job) -> bool:
        alignment = job.experience_requirement().alignment_with(
            self.ideal_max_years
        )

        return alignment == ExperienceAlignment.WITHIN_IDEAL_RANGE