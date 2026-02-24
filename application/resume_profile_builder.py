from collections import Counter
from domain.candidate_profile import CandidateProfile


class ResumeProfileBuilder:

    KNOWN_SKILLS = {
        "java",
        "spring",
        "spring boot",
        "rest",
        "sql",
        "docker",
        "aws",
        "kafka",
        "microservices",
        "react",
        "python",
        "kotlin",
    }

    def build(self, resume_text: str) -> CandidateProfile:

        normalized_text = resume_text.lower()

        skill_counts = Counter()

        for skill in self.KNOWN_SKILLS:
            if skill in normalized_text:
                skill_counts[skill] += 1

        core_skills = {}
        secondary_skills = {}

        for skill, count in skill_counts.items():
            if count >= 2:
                core_skills[skill] = 4
            else:
                secondary_skills[skill] = 2

        return CandidateProfile(
            preferred_locations=["Jacksonville", "Jax Beach"],
            remote_allowed=True,
            salary_minimum=85000,
            ideal_max_experience_years=3,
            core_skills=core_skills,
            secondary_skills=secondary_skills
        )