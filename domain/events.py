from dataclasses import dataclass


class DomainEvent:

    @classmethod
    def event_type(cls) -> str:
        return cls.__name__

    @classmethod
    def event_version(cls) -> int:
        return 1


@dataclass(frozen=True)
class JobQualified(DomainEvent):
    job_id: str
    score: int
    url: str


@dataclass(frozen=True)
class JobEvaluated(DomainEvent):
    job_id: str
    score: int
    qualified: bool