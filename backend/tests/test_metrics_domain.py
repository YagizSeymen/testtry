from __future__ import annotations

from app.domain.metrics import median_minutes


def test_median_minutes_empty_is_null() -> None:
    assert median_minutes([]) is None


def test_median_minutes_rounds_one_decimal() -> None:
    assert median_minutes([10.0, 20.0, 12.0]) == 12.0
    assert median_minutes([10.04, 10.06]) == 10.1
