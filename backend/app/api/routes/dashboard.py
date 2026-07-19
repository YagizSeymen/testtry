from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_founder_query_service
from app.schemas import DashboardFounder
from app.services import FounderQueryService

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=list[DashboardFounder])
def get_dashboard(
    service: FounderQueryService = Depends(get_founder_query_service),
) -> list[DashboardFounder]:
    return service.dashboard()
