from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_decision_service
from app.schemas.decision import AuditEventOut
from app.services.decision_service import DecisionService

router = APIRouter(tags=["audit"])


@router.get("/audit", response_model=list[AuditEventOut])
def get_audit(
    founder_id: str | None = Query(default=None),
    service: DecisionService = Depends(get_decision_service),
) -> list[AuditEventOut]:
    return service.audit(founder_id=founder_id)
