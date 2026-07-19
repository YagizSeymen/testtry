from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_thesis_service
from app.schemas import OkResponse, ThesisResponse, ThesisWriteRequest
from app.services import ThesisService

router = APIRouter(tags=["thesis"])


@router.get("/thesis", response_model=ThesisResponse)
def get_thesis(service: ThesisService = Depends(get_thesis_service)) -> ThesisResponse:
    return service.get()


@router.post("/thesis", response_model=OkResponse)
def put_thesis(
    body: ThesisWriteRequest,
    service: ThesisService = Depends(get_thesis_service),
) -> OkResponse:
    return service.replace(body.thesis)
