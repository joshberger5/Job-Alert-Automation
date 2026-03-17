def _trim_votes(votes: list[dict[str, object]]) -> list[dict[str, object]]:
    """Sort by voted_at and keep the most recent 50 records."""
    sorted_votes: list[dict[str, object]] = sorted(
        votes, key=lambda v: str(v.get("voted_at", ""))
    )
    return sorted_votes[-50:]
