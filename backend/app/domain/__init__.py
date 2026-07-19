"""Pure domain logic — no I/O, no FastAPI."""

from app.domain.founder_score import ScoreSnapshot, SignalPoint, compute_founder_score, normalize_founder_name

__all__ = [
    "ScoreSnapshot",
    "SignalPoint",
    "compute_founder_score",
    "normalize_founder_name",
]
