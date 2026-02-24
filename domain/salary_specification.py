from domain.specification import Specification


class SalaryMeetsMinimumSpecification(Specification):

    def __init__(self, minimum_salary: int):
        self.minimum_salary = minimum_salary

    def is_satisfied_by(self, job) -> bool:
        return job.salary_range().meets_minimum(
            self.minimum_salary
        )