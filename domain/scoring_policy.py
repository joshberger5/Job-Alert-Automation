import re

from domain.candidate_profile import CandidateProfile
from domain.job import Job


class ScoringPolicy:

    MINIMUM_SCORE = 7

    def evaluate(self, job: Job, profile: CandidateProfile) -> tuple[int, dict[str, int]]:
        job_content = job.normalized_content()

        total_score = 0
        breakdown: dict[str, int] = {}

        total_score += self._calculate_skill_score(
            job_content,
            profile,
            breakdown
        )

        total_score += self._calculate_missing_skill_penalty(
            job,
            profile,
            breakdown
        )

        return total_score, breakdown

    def qualifies(self, score: int) -> bool:
        return score >= self.MINIMUM_SCORE

    def _calculate_skill_score(
        self,
        job_content: str,
        profile: CandidateProfile,
        breakdown: dict[str, int],
    ) -> int:
        score = 0

        for skill, weight in profile.core_skills.items():
            if re.search(r'\b' + re.escape(skill.lower()) + r'\b', job_content):
                score += weight
                breakdown[f"core:{skill}"] = weight

        for skill, weight in profile.secondary_skills.items():
            if re.search(r'\b' + re.escape(skill.lower()) + r'\b', job_content):
                score += weight
                breakdown[f"secondary:{skill}"] = weight

        return score

    def _calculate_missing_skill_penalty(
        self,
        job: Job,
        profile: CandidateProfile,
        breakdown: dict[str, int],
    ) -> int:
        if not job.required_skills:
            return 0

        candidate_skills = {
            skill.lower()
            for skill in (
                list(profile.core_skills.keys())
                + list(profile.secondary_skills.keys())
            )
        }

        penalty = 0

        for required_skill in job.normalized_required_skills():
            if required_skill not in candidate_skills:
                penalty_value = -2
                penalty += penalty_value
                breakdown[f"missing:{required_skill}"] = penalty_value

        return penalty
