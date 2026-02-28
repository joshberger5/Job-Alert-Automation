from domain.experience_alignment import ExperienceAlignment
from domain.job import Job
from domain.specification import Specification


class ExperienceWithinIdealRangeSpecification(Specification[Job]):

    def __init__(self, ideal_max_years: int) -> None:
        self.ideal_max_years = ideal_max_years

    def is_satisfied_by(self, job: Job) -> bool:
        alignment = job.experience_requirement().alignment_with(
            self.ideal_max_years
        )

        return alignment == ExperienceAlignment.WITHIN_IDEAL_RANGE
