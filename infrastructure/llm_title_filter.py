from __future__ import annotations

import json
import re
from typing import Any

import requests

from domain.candidate_profile import CandidateProfile
from application.job_record import JobRecord

_GEMINI_URL: str = (
    "https://generativelanguage.googleapis.com/v1beta/models"
    "/gemini-2.0-flash-lite:generateContent"
)


def _build_prompt(records: list[JobRecord], profile: CandidateProfile) -> str:
    core: str = ", ".join(profile.core_skills.keys())
    max_exp: int = profile.ideal_max_experience_years
    titles_block: str = "\n".join(
        f"{i}. {r['title']} @ {r['company']}" for i, r in enumerate(records)
    )
    return (
        f"You are screening job listings for a software engineer.\n\n"
        f"Candidate profile:\n"
        f"- Core skills: {core}\n"
        f"- Experience level: 0–{max_exp} years\n\n"
        f"Review the job listings below and return a JSON array of the 0-based "
        f"indices for roles this candidate should apply to.\n\n"
        f"KEEP: software engineering roles — backend, full-stack, Java developer, "
        f"software engineer, platform engineer, DevOps, SRE, mobile, QA automation, etc.\n"
        f"REJECT: roles clearly outside software engineering — data scientist, "
        f"data engineer, ML engineer, economist, accountant, financial analyst, "
        f"designer, product manager, sales, marketing, HR, legal, operations, "
        f"recruiter, pure manual QA.\n\n"
        f"Job listings (index. title @ company):\n{titles_block}\n\n"
        f"Return ONLY a JSON array of integers, e.g. [0, 2, 5]. "
        f"An empty array [] is valid if none qualify."
    )


class GeminiTitleFilter:
    def __init__(self, api_key: str) -> None:
        self._api_key: str = api_key

    def filter_by_title(
        self, records: list[JobRecord], profile: CandidateProfile
    ) -> set[str]:
        """Return the set of job IDs from *records* the LLM considers relevant.

        Fails open — on any error the full set of IDs is returned so no jobs
        are silently dropped.
        """
        if not records:
            return set()

        try:
            prompt: str = _build_prompt(records, profile)
            response = requests.post(
                _GEMINI_URL,
                params={"key": self._api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0},
                },
                timeout=20,
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()

            raw_text: str = (
                data["candidates"][0]["content"]["parts"][0]["text"]
            )

            # LLMs sometimes wrap output in markdown fences — extract the array
            match: re.Match[str] | None = re.search(r"\[[\d,\s]*\]", raw_text)
            if not match:
                print(
                    f"  [LLM] WARNING: unexpected response format — "
                    f"{raw_text[:200]!r} — passing all through"
                )
                return {r["id"] for r in records}

            approved_indices: list[int] = json.loads(match.group())
            approved_ids: set[str] = {
                records[i]["id"]
                for i in approved_indices
                if 0 <= i < len(records)
            }

            rejected_count: int = len(records) - len(approved_ids)
            print(
                f"  [LLM] {len(approved_ids)} relevant, "
                f"{rejected_count} rejected by title"
            )
            return approved_ids

        except Exception as e:
            print(f"  [LLM] ERROR: {e} — passing all through")
            return {r["id"] for r in records}
