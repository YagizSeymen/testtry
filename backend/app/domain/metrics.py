from __future__ import annotations

from datetime import datetime
from statistics import median


def minutes_between(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 60.0


def median_minutes(values: list[float]) -> float | None:
    """Median of elapsed minutes, rounded to one decimal; null if empty (steps.md)."""
    if not values:
        return None
    return round(float(median(values)), 1)
