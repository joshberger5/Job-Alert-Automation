from typing import TypedDict


class JobRecord(TypedDict, total=False):
    id: str
    title: str
    company: str
    location: str
    remote: bool | None
    employment_type: str | None
    salary: str | None
    url: str | None
    description_length: int
    result: str
    filter_reason: str
    score: int
    score_breakdown: dict[str, int]
    qualified: bool
    llm_relevant: bool
