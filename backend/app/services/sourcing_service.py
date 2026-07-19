from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.domain.query_match import match_founder
from app.repositories.applications import ApplicationRepository
from app.repositories.founders import FounderRepository
from app.repositories.thesis import ThesisRepository
from app.schemas.sourcing import (
    ActivateResponse,
    QueryFilter,
    QueryMatch,
    QueryRequest,
    QueryResponse,
    ScanRunResponse,
)
from app.services.intelligence import IntelligenceService
from app.services.seed_service import SeedService


class SourcingService:
    def __init__(self, db: Session, intelligence: IntelligenceService | None = None) -> None:
        self._db = db
        self._founders = FounderRepository(db)
        self._thesis = ThesisRepository(db)
        self._apps = ApplicationRepository(db)
        self._ai = intelligence or IntelligenceService()

    def query(self, body: QueryRequest) -> QueryResponse:
        thesis = self._thesis.get()
        if thesis is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Thesis not configured")

        raw_filter = self._ai.parse_query(q=body.q, thesis=thesis.model_dump())
        filt = QueryFilter.model_validate(raw_filter)

        # Demo clock: use latest seeded signal window so "last 30 days" works offline.
        now = datetime(2026, 7, 18, 8, 0, tzinfo=timezone.utc)
        results: list[QueryMatch] = []
        for founder in self._founders.list_all():
            why = match_founder(founder, filt, now=now)
            if why:
                results.append(QueryMatch(founder_id=founder.id, why_matched=why))

        self._apps.add_audit(
            stage="query",
            action="query_parsed",
            detail=body.q,
            actor="system",
        )
        self._apps.save()
        return QueryResponse(filter=filt, results=results)

    def activate(self, founder_id: str) -> ActivateResponse:
        founder = self._founders.get(founder_id)
        if founder is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Founder not found")

        first_name = founder.name.split()[0] if founder.name.strip() else "there"
        theme = founder.headline or "what you are building"
        draft = (
            f"Hi {first_name} — I saw your {founder.origin} AI infrastructure work "
            f"and would like to learn {theme.lower() if theme else 'what you are building'}. "
            "This draft is for review only and will not be sent."
        )
        self._apps.add_audit(
            stage="activate",
            action="outreach_draft_created",
            detail="Outreach draft generated; not sent.",
            founder_id=founder.id,
            actor="system",
        )
        self._apps.save()
        return ActivateResponse(outreach_draft=draft)

    def scan_run(self) -> ScanRunResponse:
        """P0: always use reviewed cache / seed. Live scan is bonus later."""
        before_founders = self._founders.count_founders()
        before_signals = sum(len(f.signals) for f in self._founders.list_all())

        seeded = SeedService(self._db).seed_if_empty()

        after_founders = self._founders.count_founders()
        after_signals = sum(len(f.signals) for f in self._founders.list_all())
        new_founders = max(0, after_founders - before_founders)
        new_signals = max(0, after_signals - before_signals)

        self._apps.add_audit(
            stage="scan",
            action="loaded_cached_signals" if seeded or new_signals else "scan_cache_hit",
            detail="Source mode: reviewed cache; cache fallback: true",
            actor="system",
        )
        self._apps.save()
        return ScanRunResponse(
            new_founders=new_founders,
            new_signals=new_signals,
            cached=True,
        )
