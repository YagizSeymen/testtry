"""Pure domain logic — no I/O, no FastAPI."""

from app.domain.diligence import guard_memo_recommendation, map_trust, normalize_diligence_row
from app.domain.founder_score import (
    ScoreSnapshot,
    SignalPoint,
    compute_founder_score,
    core_person_name,
    normalize_founder_name,
)
from app.domain.metrics import median_minutes, minutes_between

__all__ = [
    "ScoreSnapshot",
    "SignalPoint",
    "compute_founder_score",
    "core_person_name",
    "guard_memo_recommendation",
    "map_trust",
    "median_minutes",
    "minutes_between",
    "normalize_diligence_row",
    "normalize_founder_name",
]
