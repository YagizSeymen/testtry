from __future__ import annotations

from datetime import datetime, timezone

from app.domain.query_match import match_founder
from app.models import Founder, Signal
from app.schemas.sourcing import QueryFilter


def test_match_founder_requires_sector_when_filtered() -> None:
    founder = Founder(
        id="f1",
        name="Ada",
        normalized_name="ada",
        headline="Technical founder",
        location="Berlin",
        origin="synthetic",
        bio=None,
    )
    founder.signals = [
        Signal(
            id="s1",
            founder_id="f1",
            ts=datetime(2026, 7, 1, tzinfo=timezone.utc),
            source="synthetic",
            text="Shipped a demo",
            url=None,
        )
    ]
    filt = QueryFilter(technical_founder=True, sectors=["AI infrastructure"], geos=[], shipped_within_days=None, prior_vc=False)
    assert match_founder(founder, filt, now=datetime(2026, 7, 18, tzinfo=timezone.utc)) == []
