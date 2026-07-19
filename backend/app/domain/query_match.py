from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import Founder
from app.schemas.sourcing import QueryFilter


def _corpus(founder: Founder) -> str:
    parts = [
        founder.name or "",
        founder.headline or "",
        founder.bio or "",
        founder.location or "",
        founder.origin or "",
    ]
    parts.extend(s.text for s in founder.signals)
    return " ".join(parts).lower()


def match_founder(founder: Founder, filt: QueryFilter, *, now: datetime | None = None) -> list[str]:
    """Deterministic Memory search through the query filter (steps.md SIDE: QUERY)."""
    why: list[str] = []
    corpus = _corpus(founder)
    now = now or datetime.now(timezone.utc)

    if filt.technical_founder is True:
        if any(term in corpus for term in ("technical", "engineer", "github", "shipped", "hackathon", "infra")):
            why.append("Technical founder")
        else:
            return []

    for sector in filt.sectors:
        tokens = [t for t in sector.lower().replace("-", " ").split() if t]
        if tokens and all(token in corpus for token in tokens):
            why.append(sector)
        elif sector.lower() in corpus:
            why.append(sector)
        else:
            return []

    for geo in filt.geos:
        if geo.lower() not in (founder.location or "").lower() and geo.lower() not in corpus:
            return []
        why.append(geo)

    if filt.shipped_within_days is not None:
        window_start = now - timedelta(days=filt.shipped_within_days)
        recent = False
        for signal in founder.signals:
            ts = signal.ts if signal.ts.tzinfo else signal.ts.replace(tzinfo=timezone.utc)
            if ts >= window_start:
                recent = True
                break
        if not recent:
            return []
        why.append("Recent product shipment")

    if filt.prior_vc is False:
        if any(term in corpus for term in ("series a", "raised venture", "backed by sequoia", "prior vc")):
            return []
        why.append("No prior VC disclosed")
    elif filt.prior_vc is True:
        if not any(term in corpus for term in ("funded", "venture", "raised")):
            return []
        why.append("Prior VC signal")

    # If filter is empty-ish, still return a soft match for dashboard search UX.
    if not why and not any(
        [
            filt.technical_founder is not None,
            filt.sectors,
            filt.geos,
            filt.shipped_within_days is not None,
            filt.prior_vc is not None,
        ]
    ):
        why.append("Listed in Memory")

    return why
