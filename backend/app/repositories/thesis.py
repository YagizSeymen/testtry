from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import ThesisRow
from app.schemas import Thesis


class ThesisRepository:
    SINGLETON_ID = 1

    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self) -> Thesis | None:
        row = self._db.get(ThesisRow, self.SINGLETON_ID)
        if row is None:
            return None
        return Thesis(
            sectors=json.loads(row.sectors_json),
            stage=row.stage,
            geo=json.loads(row.geo_json),
            check_size=row.check_size,
            risk_appetite=row.risk_appetite,  # type: ignore[arg-type]
        )

    def upsert(self, thesis: Thesis) -> Thesis:
        row = self._db.get(ThesisRow, self.SINGLETON_ID)
        now = datetime.now(timezone.utc)
        if row is None:
            row = ThesisRow(
                id=self.SINGLETON_ID,
                sectors_json=json.dumps(thesis.sectors),
                stage=thesis.stage,
                geo_json=json.dumps(thesis.geo),
                check_size=thesis.check_size,
                risk_appetite=thesis.risk_appetite,
                updated_at=now,
            )
            self._db.add(row)
        else:
            row.sectors_json = json.dumps(thesis.sectors)
            row.stage = thesis.stage
            row.geo_json = json.dumps(thesis.geo)
            row.check_size = thesis.check_size
            row.risk_appetite = thesis.risk_appetite
            row.updated_at = now
        self._db.commit()
        return thesis
