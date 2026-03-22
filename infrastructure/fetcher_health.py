"""Tracks consecutive failure counts per fetcher across runs.

Persists to fetcher_health.json so the auto-repair workflow can decide
whether a fetcher has failed enough times to warrant a fix attempt.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import TypedDict, cast

from application.fetcher_result import FetcherFailure

_DEFAULT_PATH: str = "fetcher_health.json"


class FetcherHealthRecord(TypedDict):
    consecutive_failures: int
    last_error: str | None
    last_failed_at: str | None


FetcherHealth = dict[str, FetcherHealthRecord]


def read_health(path: str = _DEFAULT_PATH) -> FetcherHealth:
    """Return persisted health data, or {} if the file does not exist."""
    p: Path = Path(path)
    if not p.exists():
        return {}
    return cast(FetcherHealth, json.loads(p.read_text(encoding="utf-8")))


def update_health(
    current: FetcherHealth,
    failures: list[FetcherFailure],
    all_labels: list[str],
    now: datetime | None = None,
) -> FetcherHealth:
    """Return updated health data without mutating current.

    - Fetchers in failures: consecutive_failures += 1, last_error/last_failed_at set.
    - Fetchers in all_labels but NOT in failures: consecutive_failures reset to 0.
    - Fetchers not in all_labels: left unchanged (handles removed fetchers gracefully).
    """
    ts: str = (now or datetime.now()).isoformat(timespec="seconds")
    failed_map: dict[str, FetcherFailure] = {f["company"]: f for f in failures}
    updated: FetcherHealth = dict(current)

    for label in all_labels:
        if label in failed_map:
            fail: FetcherFailure = failed_map[label]
            prev_count: int = updated[label]["consecutive_failures"] if label in updated else 0
            updated[label] = {
                "consecutive_failures": prev_count + 1,
                "last_error": fail.get("error"),
                "last_failed_at": ts,
            }
        elif label in updated:
            prev: FetcherHealthRecord = updated[label]
            updated[label] = {
                "consecutive_failures": 0,
                "last_error": prev["last_error"],
                "last_failed_at": prev["last_failed_at"],
            }

    return updated


def write_health(data: FetcherHealth, path: str = _DEFAULT_PATH) -> None:
    """Write health data to disk as formatted JSON."""
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
# test
