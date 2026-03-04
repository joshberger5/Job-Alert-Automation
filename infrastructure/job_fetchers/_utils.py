def infer_remote(location: str) -> bool | None:
    """Return True if the location string indicates remote work, None otherwise.

    Returns None (not False) — only fetchers with definitive on-site evidence
    should set remote=False.
    """
    return True if location and "remote" in location.lower() else None
