from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_decision_service
from app.schemas.decision import DecideRequest, DecideResponse, DecisionQueueItem
from app.services.decision_service import DecisionService

router = APIRouter(tags=["decisions"])


@router.get("/decisions/queue", response_model=list[DecisionQueueItem])
def decisions_queue(
    service: DecisionService = Depends(get_decision_service),
) -> list[DecisionQueueItem]:
    return service.queue()


@router.post("/decisions/{application_id}/decide", response_model=DecideResponse)
def decide(
    application_id: str,
    body: DecideRequest,
    service: DecisionService = Depends(get_decision_service),
) -> DecideResponse:
    return service.decide(application_id, body)
