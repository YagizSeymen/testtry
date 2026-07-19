from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.domain.metrics import median_minutes, minutes_between
from app.repositories.applications import ApplicationRepository, loads
from app.repositories.founders import FounderRepository
from app.schemas.application import Recommendation
from app.schemas.decision import (
    AuditEventOut,
    DecideRequest,
    DecideResponse,
    DecisionQueueItem,
    FunnelMetrics,
    MetricsResponse,
)


class DecisionService:
    """Human gate, audit listing, and utility metrics."""

    def __init__(self, db: Session) -> None:
        self._apps = ApplicationRepository(db)
        self._founders = FounderRepository(db)

    def queue(self) -> list[DecisionQueueItem]:
        items: list[DecisionQueueItem] = []
        for app in self._apps.list_memo_ready_open():
            memo = loads(app.memo_json) or {}
            recommendation = Recommendation.model_validate(memo.get("recommendation"))
            items.append(
                DecisionQueueItem(
                    application_id=app.id,
                    company=app.company_name,
                    recommendation=recommendation,
                    memo_id=str(memo.get("memo_id") or ""),
                )
            )
        return items

    def decide(self, application_id: str, body: DecideRequest) -> DecideResponse:
        app = self._apps.get(application_id)
        if app is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
        if not app.memo_json:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Decision requires memo_ready",
            )
        if app.status != "open":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Application already {app.status}",
            )

        new_status = "approved" if body.action == "approve" else "rejected"
        now = datetime.now(timezone.utc)
        app.status = new_status
        app.decided_at = now
        app.decided_by = body.approver.strip()

        event = self._apps.add_audit(
            stage="decision",
            action=new_status,
            detail=f"Human {new_status} the $100K recommendation.",
            founder_id=app.founder_id,
            application_id=app.id,
            actor=body.approver.strip(),
        )
        self._apps.save()
        return DecideResponse(status=new_status, audit_id=f"audit_{event.id}")

    def audit(self, founder_id: str | None = None) -> list[AuditEventOut]:
        return [
            AuditEventOut(
                ts=event.ts if event.ts.tzinfo else event.ts.replace(tzinfo=timezone.utc),
                stage=event.stage,
                actor=event.actor,
                action=event.action,
                detail=event.detail,
            )
            for event in self._apps.list_audit(founder_id=founder_id)
        ]

    def metrics(self) -> MetricsResponse:
        founders = self._founders.list_all()
        apps = self._apps.list_all_apps()

        sourced = len([f for f in founders if f.signals])
        screened = len({a.id for a in apps if a.axes_json})
        diligenced = len({a.id for a in apps if a.diligence_json})
        decided = len({a.id for a in apps if a.status in {"approved", "rejected"}})

        elapsed: list[float] = []
        for app in apps:
            if app.status not in {"approved", "rejected"} or app.decided_at is None:
                continue
            signals = app.founder.signals
            if not signals:
                continue
            first_signal_at = min(s.ts for s in signals)
            if first_signal_at.tzinfo is None:
                first_signal_at = first_signal_at.replace(tzinfo=timezone.utc)
            decided_at = app.decided_at if app.decided_at.tzinfo else app.decided_at.replace(tzinfo=timezone.utc)
            elapsed.append(minutes_between(first_signal_at, decided_at))

        return MetricsResponse(
            signal_to_decision_min=median_minutes(elapsed),
            funnel=FunnelMetrics(
                sourced=sourced,
                screened=screened,
                diligenced=diligenced,
                decided=decided,
            ),
        )
