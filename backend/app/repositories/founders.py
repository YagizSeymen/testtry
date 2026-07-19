from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Application, Founder, ScoreSnapshotRow, Signal


class FounderRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_all(self) -> list[Founder]:
        stmt = (
            select(Founder)
            .options(
                selectinload(Founder.signals),
                selectinload(Founder.score_snapshots),
                selectinload(Founder.applications),
            )
            .order_by(Founder.name)
        )
        return list(self._db.scalars(stmt).all())

    def get(self, founder_id: str) -> Founder | None:
        stmt = (
            select(Founder)
            .where(Founder.id == founder_id)
            .options(
                selectinload(Founder.signals),
                selectinload(Founder.score_snapshots),
                selectinload(Founder.applications),
            )
        )
        return self._db.scalars(stmt).first()

    def get_by_normalized_name(self, normalized_name: str) -> Founder | None:
        stmt = select(Founder).where(Founder.normalized_name == normalized_name)
        return self._db.scalars(stmt).first()

    def add(self, founder: Founder) -> Founder:
        self._db.add(founder)
        return founder

    def add_signal(self, signal: Signal) -> Signal:
        self._db.add(signal)
        return signal

    def add_score_snapshot(self, snapshot: ScoreSnapshotRow) -> ScoreSnapshotRow:
        self._db.add(snapshot)
        return snapshot

    def add_application(self, application: Application) -> Application:
        self._db.add(application)
        return application

    def commit(self) -> None:
        self._db.commit()

    def count_founders(self) -> int:
        return len(self._db.scalars(select(Founder.id)).all())
