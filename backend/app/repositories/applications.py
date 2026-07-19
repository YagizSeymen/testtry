from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Application, AuditEvent, Founder


class ApplicationRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, application_id: str) -> Application | None:
        stmt = (
            select(Application)
            .where(Application.id == application_id)
            .options(selectinload(Application.founder).selectinload(Founder.signals))
        )
        return self._db.scalars(stmt).first()

    def add(self, application: Application) -> Application:
        self._db.add(application)
        return application

    def save(self) -> None:
        self._db.commit()

    def list_memo_ready_open(self) -> list[Application]:
        stmt = (
            select(Application)
            .where(Application.status == "open")
            .where(Application.memo_json.is_not(None))
            .options(selectinload(Application.founder))
            .order_by(Application.created_at)
        )
        return list(self._db.scalars(stmt).all())

    def list_all_apps(self) -> list[Application]:
        stmt = select(Application).options(
            selectinload(Application.founder).selectinload(Founder.signals)
        )
        return list(self._db.scalars(stmt).all())

    def list_audit(self, *, founder_id: str | None = None) -> list[AuditEvent]:
        stmt = select(AuditEvent).order_by(AuditEvent.ts.asc(), AuditEvent.id.asc())
        if founder_id:
            stmt = stmt.where(AuditEvent.founder_id == founder_id)
        return list(self._db.scalars(stmt).all())

    def add_audit(
        self,
        *,
        stage: str,
        action: str,
        detail: str,
        founder_id: str | None = None,
        application_id: str | None = None,
        actor: str = "system",
    ) -> AuditEvent:
        event = AuditEvent(
            ts=datetime.now(timezone.utc),
            stage=stage,
            actor=actor,
            action=action,
            detail=detail,
            founder_id=founder_id,
            application_id=application_id,
        )
        self._db.add(event)
        self._db.flush()
        return event


def dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), default=str)


def loads(value: str | None) -> Any:
    if value is None:
        return None
    return json.loads(value)


def new_application_id() -> str:
    return f"app_{uuid4().hex[:12]}"


def new_founder_id() -> str:
    return f"fndr_{uuid4().hex[:12]}"
