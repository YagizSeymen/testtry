from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Founder
from app.repositories import FounderRepository
from app.schemas import (
    DashboardFounder,
    FounderDetailResponse,
    ProfileOut,
    ScoreHistoryItem,
    SignalOut,
)


class FounderQueryService:
    """Read-side founder/dashboard queries over Memory."""

    def __init__(self, db: Session) -> None:
        self._repo = FounderRepository(db)

    def dashboard(self) -> list[DashboardFounder]:
        return [self._to_dashboard_row(f) for f in self._repo.list_all()]

    def get_detail(self, founder_id: str) -> FounderDetailResponse:
        founder = self._repo.get(founder_id)
        if founder is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Founder not found")
        signals = sorted(founder.signals, key=lambda s: s.ts, reverse=True)
        history = sorted(founder.score_snapshots, key=lambda s: s.ts)
        return FounderDetailResponse(
            profile=ProfileOut(
                founder_id=founder.id,
                name=founder.name,
                headline=founder.headline,
                location=founder.location,
                origin=founder.origin,  # type: ignore[arg-type]
                bio=founder.bio,
            ),
            signals=[
                SignalOut(
                    signal_id=s.id,
                    ts=_ensure_aware(s.ts),
                    source=s.source,
                    text=s.text,
                    url=s.url,
                )
                for s in signals
            ],
            score_history=[
                ScoreHistoryItem(ts=_ensure_aware(h.ts), score=h.score, band=h.band) for h in history
            ],
            applications=[a.id for a in founder.applications],
        )

    def _to_dashboard_row(self, founder: Founder) -> DashboardFounder:
        latest = max(founder.score_snapshots, key=lambda s: s.ts, default=None)
        if latest is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Founder {founder.id} has no score snapshot",
            )
        # Prefer earliest shipping signals for dashboard chips (demo narrative).
        top = sorted(founder.signals, key=lambda s: s.ts)[:2]
        has_open = any(a.status == "open" for a in founder.applications)
        return DashboardFounder(
            founder_id=founder.id,
            name=founder.name,
            origin=founder.origin,  # type: ignore[arg-type]
            founder_score=latest.score,
            band=latest.band,
            trend=latest.trend,  # type: ignore[arg-type]
            top_signals=[_format_top_signal(s.source, s.text) for s in top],
            has_open_app=has_open,
        )


def _format_top_signal(source: str, text: str) -> str:
    label = "Synthetic" if source.strip().lower() == "synthetic" else source
    # Keep dashboard chips short.
    short = text if len(text) <= 80 else text[:77] + "..."
    if source.strip().lower() == "synthetic" and not short.startswith("["):
        return f"[{label}] {short}"
    return short


def _ensure_aware(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts
