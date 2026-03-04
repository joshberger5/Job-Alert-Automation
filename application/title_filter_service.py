from typing import Protocol

from domain.candidate_profile import CandidateProfile
from application.job_record import JobRecord


class TitleFilter(Protocol):
    def filter_by_title(
        self, records: list[JobRecord], profile: CandidateProfile
    ) -> set[str]:
        ...


class TitleFilterService:
    """Orchestrates the two-stage title filter pipeline.

    Always runs the keyword filter first. Runs the optional LLM filter only
    on keyword-approved records to conserve API quota.

    Qualified jobs rejected by either filter are re-marked "llm_filtered".
    Scored-out jobs approved by the LLM gain ``llm_relevant=True``.
    """

    def __init__(
        self,
        keyword_filter: TitleFilter,
        llm_filter: TitleFilter | None = None,
    ) -> None:
        self._keyword_filter: TitleFilter = keyword_filter
        self._llm_filter: TitleFilter | None = llm_filter

    def apply(
        self, records: list[JobRecord], profile: CandidateProfile
    ) -> list[JobRecord]:
        post_filter: list[JobRecord] = [
            r for r in records if r.get("result") in ("qualified", "scored_out")
        ]

        # Stage 1: keyword filter (always runs)
        kw_approved_ids: set[str] = self._keyword_filter.filter_by_title(
            post_filter, profile
        )
        for r in records:
            if r.get("result") == "qualified" and r["id"] not in kw_approved_ids:
                r["result"] = "llm_filtered"

        # Stage 2: LLM filter (optional, only on keyword-approved records)
        if self._llm_filter is not None:
            llm_candidates: list[JobRecord] = [
                r for r in records
                if r.get("result") in ("qualified", "scored_out")
                and r["id"] in kw_approved_ids
            ]
            if llm_candidates:
                approved_ids: set[str] = self._llm_filter.filter_by_title(
                    llm_candidates, profile
                )
                for r in records:
                    if r.get("result") == "qualified" and r["id"] not in approved_ids:
                        r["result"] = "llm_filtered"
                    elif r.get("result") == "scored_out" and r["id"] in approved_ids:
                        r["llm_relevant"] = True

        return records
