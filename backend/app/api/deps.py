from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.application_service import ApplicationService
from app.services.decision_service import DecisionService
from app.services.founder_service import FounderQueryService
from app.services.sourcing_service import SourcingService
from app.services.thesis_service import ThesisService


def get_thesis_service(db: Session = Depends(get_db)) -> Generator[ThesisService, None, None]:
    yield ThesisService(db)


def get_founder_query_service(
    db: Session = Depends(get_db),
) -> Generator[FounderQueryService, None, None]:
    yield FounderQueryService(db)


def get_application_service(
    db: Session = Depends(get_db),
) -> Generator[ApplicationService, None, None]:
    yield ApplicationService(db)


def get_decision_service(
    db: Session = Depends(get_db),
) -> Generator[DecisionService, None, None]:
    yield DecisionService(db)


def get_sourcing_service(
    db: Session = Depends(get_db),
) -> Generator[SourcingService, None, None]:
    yield SourcingService(db)
