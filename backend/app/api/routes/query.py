from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_sourcing_service
from app.schemas.sourcing import QueryRequest, QueryResponse, ScanRunResponse
from app.services.sourcing_service import SourcingService

router = APIRouter(tags=["sourcing"])


@router.post("/query", response_model=QueryResponse)
def post_query(
    body: QueryRequest,
    service: SourcingService = Depends(get_sourcing_service),
) -> QueryResponse:
    return service.query(body)


@router.post("/scan/run", response_model=ScanRunResponse)
def post_scan_run(
    service: SourcingService = Depends(get_sourcing_service),
) -> ScanRunResponse:
    return service.scan_run()
