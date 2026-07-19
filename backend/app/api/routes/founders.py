from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_founder_query_service, get_sourcing_service
from app.schemas import FounderDetailResponse
from app.schemas.sourcing import ActivateResponse
from app.services import FounderQueryService
from app.services.sourcing_service import SourcingService

router = APIRouter(tags=["founders"])


@router.get("/founders/{founder_id}", response_model=FounderDetailResponse)
def get_founder(
    founder_id: str,
    service: FounderQueryService = Depends(get_founder_query_service),
) -> FounderDetailResponse:
    return service.get_detail(founder_id)


@router.post("/founders/{founder_id}/activate", response_model=ActivateResponse)
def activate_founder(
    founder_id: str,
    service: SourcingService = Depends(get_sourcing_service),
) -> ActivateResponse:
    return service.activate(founder_id)
