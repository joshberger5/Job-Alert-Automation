from anthropic import Anthropic
from domain.candidate_profile import CandidateProfile


_EXTRACT_SKILLS_TOOL = {
    "name": "extract_skills",
    "description": "Extract and classify technical skills from a resume",
    "input_schema": {
        "type": "object",
        "properties": {
            "core_skills": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Technologies, languages, and frameworks the candidate "
                    "has significant, repeated, or primary experience with"
                ),
            },
            "secondary_skills": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Technologies the candidate has some exposure to "
                    "but are not their primary expertise"
                ),
            },
        },
        "required": ["core_skills", "secondary_skills"],
    },
}


class ResumeProfileBuilder:

    def __init__(self):
        self._client = Anthropic()

    def build(self, resume_text: str) -> CandidateProfile:
        response = self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            tools=[_EXTRACT_SKILLS_TOOL],
            tool_choice={"type": "tool", "name": "extract_skills"},
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Extract and classify the technical skills "
                        f"from this resume:\n\n{resume_text}"
                    ),
                }
            ],
        )

        tool_use = next(b for b in response.content if b.type == "tool_use")
        data = tool_use.input

        core_skills = {skill.lower(): 4 for skill in data["core_skills"]}
        secondary_skills = {skill.lower(): 2 for skill in data["secondary_skills"]}

        return CandidateProfile(
            preferred_locations=["Jacksonville", "Jax Beach"],
            remote_allowed=True,
            salary_minimum=85000,
            ideal_max_experience_years=3,
            core_skills=core_skills,
            secondary_skills=secondary_skills,
        )