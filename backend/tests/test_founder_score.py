from __future__ import annotations

from datetime import datetime, timezone

from app.domain import SignalPoint, compute_founder_score, normalize_founder_name


def test_normalize_founder_name_strips_spaces_and_punctuation() -> None:
    assert normalize_founder_name("Maya Chen (Synthetic)") == "mayachensynthetic"
    assert normalize_founder_name("Maya-Chen") == "mayachen"
    assert normalize_founder_name("  Ada  Lovelace ") == "adalovelace"


def test_founder_score_matches_fixture_golden_case() -> None:
    """Six synthetic signals, one source, one in last 30d → 59 ± 22 (fixtures README)."""
    signals = [
        SignalPoint(ts=_ts("2026-06-27T09:00:00Z"), source="synthetic"),
        SignalPoint(ts=_ts("2026-05-30T18:00:00Z"), source="synthetic"),
        SignalPoint(ts=_ts("2026-05-20T12:00:00Z"), source="synthetic"),
        SignalPoint(ts=_ts("2026-05-10T12:00:00Z"), source="synthetic"),
        SignalPoint(ts=_ts("2026-04-10T16:00:00Z"), source="synthetic"),
        SignalPoint(ts=_ts("2026-03-01T20:00:00Z"), source="synthetic"),
    ]
    snap = compute_founder_score(
        signals,
        snapshot_ts=_ts("2026-07-18T08:00:00Z"),
        previous_score=55,
    )
    assert snap.score == 59
    assert snap.band == 22
    assert snap.n_signals == 6
    assert snap.source_diversity == 1
    assert snap.signals_last_30d == 1
    assert snap.trend == "up"


def _ts(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(timezone.utc)
