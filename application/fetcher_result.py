from typing import TypedDict


class FetcherFailure(TypedDict, total=False):
    company: str
    error: str    # 'TIMEOUT' for wall-clock timeout; str(exception) otherwise
    attempts: int  # 1 = timeout (no retry); 2 = both attempts exhausted
