from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_decision_service
from app.schemas.decision import MetricsResponse
from app.services.decision_service import DecisionService

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_model=MetricsResponse)
def get_metrics(
    service: DecisionService = Depends(get_decision_service),
) -> MetricsResponse:
    return service.metrics()
