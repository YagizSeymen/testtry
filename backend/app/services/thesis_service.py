from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories import ThesisRepository
from app.schemas import OkResponse, Thesis, ThesisResponse


class ThesisService:
    def __init__(self, db: Session) -> None:
        self._repo = ThesisRepository(db)

    def get(self) -> ThesisResponse:
        thesis = self._repo.get()
        if thesis is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thesis not configured")
        return ThesisResponse(thesis=thesis)

    def replace(self, thesis: Thesis) -> OkResponse:
        self._repo.upsert(thesis)
        return OkResponse(ok=True)
