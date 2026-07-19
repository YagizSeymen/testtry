from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_application_service
from app.schemas.application import (
    ApplicationAggregate,
    ApplicationCreateRequest,
    ApplicationCreateResponse,
    Axes,
    Diligence,
    Memo,
)
from app.services.application_service import ApplicationService

router = APIRouter(tags=["applications"])


@router.post("/applications", response_model=ApplicationCreateResponse)
def create_application(
    body: ApplicationCreateRequest,
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationCreateResponse:
    return service.create(body)


@router.get("/applications/{application_id}", response_model=ApplicationAggregate)
def get_application(
    application_id: str,
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationAggregate:
    return service.get(application_id)


@router.post("/applications/{application_id}/screen", response_model=Axes)
def screen_application(
    application_id: str,
    service: ApplicationService = Depends(get_application_service),
) -> Axes:
    return service.screen(application_id)


@router.post("/applications/{application_id}/diligence", response_model=Diligence)
def diligence_application(
    application_id: str,
    service: ApplicationService = Depends(get_application_service),
) -> Diligence:
    return service.diligence(application_id)


@router.post("/applications/{application_id}/memo", response_model=Memo)
def memo_application(
    application_id: str,
    service: ApplicationService = Depends(get_application_service),
) -> Memo:
    return service.memo(application_id)
