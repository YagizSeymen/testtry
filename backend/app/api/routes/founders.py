from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_founder_query_service
from app.schemas import FounderDetailResponse
from app.services import FounderQueryService

router = APIRouter(tags=["founders"])


@router.get("/founders/{founder_id}", response_model=FounderDetailResponse)
def get_founder(
    founder_id: str,
    service: FounderQueryService = Depends(get_founder_query_service),
) -> FounderDetailResponse:
    return service.get_detail(founder_id)
