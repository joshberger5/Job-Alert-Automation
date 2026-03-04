import re

from domain.candidate_profile import CandidateProfile


_SKILLS_SECTION = re.compile(
    r'Technical Skills?\s*\n(.*?)(?=\n(?:Experience|Education|Projects|Summary|Certifications)\b|\Z)',
    re.DOTALL | re.IGNORECASE,
)

_CATEGORY_LINE = re.compile(r'^[^:\n]+:\s*(.+)$', re.MULTILINE)


class ResumeProfileBuilder:

    def build(self, resume_text: str) -> CandidateProfile:
        primary_skills, other_skills = self._extract_skills(resume_text)

        core_skills: dict[str, int] = {skill.lower(): 4 for skill in primary_skills}
        secondary_skills: dict[str, int] = {skill.lower(): 2 for skill in other_skills}

        return CandidateProfile(
            preferred_locations=["Jacksonville", "Jacksonville Beach"],
            remote_allowed=True,
            ideal_max_experience_years=3,
            core_skills=core_skills,
            secondary_skills=secondary_skills,
            open_to_contract=False,
        )

    def _extract_skills(self, resume_text: str) -> tuple[list[str], list[str]]:
        section_match = _SKILLS_SECTION.search(resume_text)
        if not section_match:
            return [], []

        categories = []
        for line_match in _CATEGORY_LINE.finditer(section_match.group(1)):
            items = [s.strip() for s in line_match.group(1).split(',')]
            categories.append([s for s in items if s])

        if not categories:
            return [], []

        # First category (e.g. Languages) = primary skills → core weight
        # Remaining categories = supporting skills → secondary weight
        primary = categories[0]
        secondary = [skill for cat in categories[1:] for skill in cat]
        return primary, secondary

