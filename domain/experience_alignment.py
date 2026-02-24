from enum import Enum


class ExperienceAlignment(Enum):
    UNKNOWN = "unknown"
    WITHIN_IDEAL_RANGE = "within_ideal_range"
    MODERATE_GAP = "moderate_gap"
    LARGE_GAP = "large_gap"