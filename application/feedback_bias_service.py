import json
import re
from pathlib import Path
from typing import cast

FEEDBACK_WEIGHT: float = 0.5
_FEEDBACK_PATH: Path = Path("feedback.json")  # relative to CWD (project root)
_THRESHOLD: int = 3


class FeedbackBiasService:

    def __init__(self) -> None:
        self._bias_map: dict[str, int] = self._load_bias_map()

    def _load_bias_map(self) -> dict[str, int]:
        if not _FEEDBACK_PATH.exists():
            return {}
        try:
            with open(_FEEDBACK_PATH, "r", encoding="utf-8") as f:
                votes: list[dict[str, object]] = json.load(f)
            bias: dict[str, int] = {}
            for entry in votes:
                vote_raw: object = entry.get("vote", 0)
                vote: int
                if str(vote_raw) in ("+1", "1"):
                    vote = 1
                elif str(vote_raw) in ("-1",):
                    vote = -1
                else:
                    try:
                        numeric: float = float(str(vote_raw))
                        int_val: int = int(numeric)
                        vote = 1 if int_val > 0 else -1
                    except (ValueError, TypeError):
                        continue
                reasons_raw: list[object] = cast(list[object], entry.get("reasons", []))
                for raw_reason in reasons_raw:
                    token: str = str(raw_reason).strip().lower()
                    if token:
                        bias[token] = bias.get(token, 0) + vote
            return bias
        except Exception:
            return {}

    def apply(
        self,
        base_score: int,
        job_content: str,
        base_breakdown: dict[str, int],
    ) -> tuple[int, dict[str, int], float]:
        """Apply feedback bias multiplier. Returns (final_score, breakdown, clamped_multiplier)."""
        if not self._bias_map:
            return base_score, base_breakdown, 1.0

        multiplier: float = 1.0
        content_lower: str = job_content.lower()
        for token, net_votes in self._bias_map.items():
            if abs(net_votes) < _THRESHOLD:
                continue
            if re.search(r"\b" + re.escape(token) + r"\b", content_lower):
                adjustment: float = net_votes * FEEDBACK_WEIGHT
                multiplier += adjustment

        clamped: float = max(0.5, min(2.0, multiplier))
        final_score: int = round(base_score * clamped)
        breakdown: dict[str, int] = dict(base_breakdown)
        breakdown["feedback_score_delta"] = final_score - base_score
        return final_score, breakdown, clamped
