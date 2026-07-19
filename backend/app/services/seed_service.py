from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain import normalize_founder_name
from app.models import Application, AuditEvent, Founder, ScoreSnapshotRow, Signal
from app.repositories import FounderRepository, ThesisRepository
from app.schemas import Thesis


class SeedService:
    """Load reviewed fixtures into Memory when the DB is empty."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._founders = FounderRepository(db)
        self._thesis = ThesisRepository(db)
        self._fixtures = get_settings().fixtures_dir

    def seed_if_empty(self) -> bool:
        if self._founders.count_founders() > 0 and self._thesis.get() is not None:
            return False
        self._seed_thesis()
        self._seed_maya_chen()
        self._db.commit()
        return True

    def _seed_thesis(self) -> None:
        if self._thesis.get() is not None:
            return
        payload = json.loads((self._fixtures / "get_thesis.json").read_text())
        self._thesis.upsert(Thesis.model_validate(payload["thesis"]))

    def _seed_maya_chen(self) -> None:
        if self._founders.get("fndr_syn_001") is not None:
            return

        detail = json.loads((self._fixtures / "get_founder.json").read_text())
        profile = detail["profile"]
        founder = Founder(
            id=profile["founder_id"],
            name=profile["name"],
            normalized_name=normalize_founder_name(profile["name"]),
            headline=profile.get("headline"),
            location=profile.get("location"),
            origin=profile["origin"],
            bio=profile.get("bio"),
        )
        self._founders.add(founder)

        for raw in detail["signals"]:
            self._founders.add_signal(
                Signal(
                    id=raw["signal_id"],
                    founder_id=founder.id,
                    ts=_parse_ts(raw["ts"]),
                    source=raw["source"],
                    text=raw["text"],
                    url=raw.get("url"),
                )
            )

        # Reviewed score history from fixtures (latest 59±22, trend up).
        # New signals at runtime use domain.compute_founder_score.
        previous_score: int | None = None
        for raw_hist in detail["score_history"]:
            score = int(raw_hist["score"])
            if previous_score is None:
                trend = "flat"
            else:
                delta = score - previous_score
                trend = "up" if delta >= 3 else "down" if delta <= -3 else "flat"
            self._founders.add_score_snapshot(
                ScoreSnapshotRow(
                    founder_id=founder.id,
                    ts=_parse_ts(raw_hist["ts"]),
                    score=score,
                    band=int(raw_hist["band"]),
                    trend=trend,
                )
            )
            previous_score = score

        for app_id in detail.get("applications", []):
            self._founders.add_application(
                Application(
                    id=app_id,
                    founder_id=founder.id,
                    company_name="NeuralKit (Synthetic)",
                    status="open",
                    deck_text="",
                    created_at=datetime.now(timezone.utc),
                    claims_json="[]",
                )
            )

        self._db.add(
            AuditEvent(
                ts=datetime.now(timezone.utc),
                stage="ingest",
                actor="system",
                action="loaded_cached_signals",
                detail="Seeded synthetic founder from data/fixtures/get_founder.json",
                founder_id=founder.id,
            )
        )


def _parse_ts(value: str) -> datetime:
    # Fixtures use ...Z
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)
