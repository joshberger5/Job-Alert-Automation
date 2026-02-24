from dataclasses import dataclass, field
from typing import List
from domain.salary_range import SalaryRange
from domain.experience_requirement import ExperienceRequirement


@dataclass
class Job:
    id: str
    title: str
    company: str
    location: str
    description: str
    salary: str | None = None
    url: str | None = None
    required_skills: List[str] = field(default_factory=list)

    def normalized_content(self) -> str:
        return f"{self.title} {self.description}".lower()

    def salary_range(self) -> SalaryRange:
        return SalaryRange.from_raw(self.salary)

    def experience_requirement(self) -> ExperienceRequirement:
        return ExperienceRequirement.from_job_content(
            self.normalized_content()
        )

    def normalized_required_skills(self) -> List[str]:
        return [skill.lower() for skill in self.required_skills]