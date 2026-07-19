from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

Trend = Literal["up", "flat", "down"]


def normalize_founder_name(name: str) -> str:
    """Person identity key: lowercase, strip spaces and punctuation (steps.md)."""
    lowered = name.strip().lower()
    return re.sub(r"[\s\W_]+", "", lowered, flags=re.UNICODE)


@dataclass(frozen=True)
class SignalPoint:
    """Minimal signal shape for scoring (ts + source)."""

    ts: datetime
    source: str


@dataclass(frozen=True)
class ScoreSnapshot:
    score: int
    band: int
    trend: Trend
    n_signals: int
    source_diversity: int
    signals_last_30d: int


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def compute_founder_score(
    signals: list[SignalPoint],
    *,
    snapshot_ts: datetime,
    previous_score: int | None = None,
) -> ScoreSnapshot:
    """Deterministic Founder Score (steps.md §4). Uses fixture timestamps, not wall clock."""
    if snapshot_ts.tzinfo is None:
        snapshot_ts = snapshot_ts.replace(tzinfo=timezone.utc)

    # Only signals observed at or before the snapshot participate.
    eligible = [s for s in signals if _as_utc(s.ts) <= snapshot_ts]
    n_signals = len(eligible)
    sources = {s.source.strip().lower() for s in eligible if s.source.strip()}
    source_diversity = len(sources)

    window_start = snapshot_ts - timedelta(days=30)
    signals_last_30d = sum(1 for s in eligible if window_start <= _as_utc(s.ts) <= snapshot_ts)

    raw = 35 + 8 * source_diversity + 4 * signals_last_30d + 2 * n_signals
    score = int(_clamp(raw, 0, 100))
    band = int(math.floor(_clamp(60 / math.sqrt(n_signals + 1), 5, 30)))

    if previous_score is None:
        trend: Trend = "flat"
    else:
        delta = score - previous_score
        if delta >= 3:
            trend = "up"
        elif delta <= -3:
            trend = "down"
        else:
            trend = "flat"

    return ScoreSnapshot(
        score=score,
        band=band,
        trend=trend,
        n_signals=n_signals,
        source_diversity=source_diversity,
        signals_last_30d=signals_last_30d,
    )


def _as_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)
