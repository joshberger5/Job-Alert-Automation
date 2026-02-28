from domain.job import Job
from domain.specification import Specification


class SalaryMeetsMinimumSpecification(Specification[Job]):

    def __init__(self, minimum_salary: int) -> None:
        self.minimum_salary = minimum_salary

    def is_satisfied_by(self, job: Job) -> bool:
        return job.salary_range().meets_minimum(
            self.minimum_salary
        )
