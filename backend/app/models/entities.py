from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ThesisRow(Base):
    """Single-fund thesis store (exactly one logical row; id always 1)."""

    __tablename__ = "thesis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sectors_json: Mapped[str] = mapped_column(Text, nullable=False)
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    geo_json: Mapped[str] = mapped_column(Text, nullable=False)
    check_size: Mapped[int] = mapped_column(Integer, nullable=False, default=100_000)
    risk_appetite: Mapped[str] = mapped_column(String(16), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Founder(Base):
    __tablename__ = "founders"
    __table_args__ = (UniqueConstraint("normalized_name", name="uq_founders_normalized_name"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    headline: Mapped[str | None] = mapped_column(String(512), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    origin: Mapped[str] = mapped_column(String(32), nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)

    signals: Mapped[list[Signal]] = relationship(back_populates="founder", cascade="all, delete-orphan")
    score_snapshots: Mapped[list[ScoreSnapshotRow]] = relationship(
        back_populates="founder", cascade="all, delete-orphan"
    )
    applications: Mapped[list[Application]] = relationship(back_populates="founder")


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    founder_id: Mapped[str] = mapped_column(ForeignKey("founders.id"), nullable=False, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    founder: Mapped[Founder] = relationship(back_populates="signals")


class ScoreSnapshotRow(Base):
    __tablename__ = "score_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    founder_id: Mapped[str] = mapped_column(ForeignKey("founders.id"), nullable=False, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    band: Mapped[int] = mapped_column(Integer, nullable=False)
    trend: Mapped[str] = mapped_column(String(8), nullable=False)

    founder: Mapped[Founder] = relationship(back_populates="score_snapshots")


class Application(Base):
    """Inbound opportunity. Stage readiness = nullable JSON stage payloads."""

    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    founder_id: Mapped[str] = mapped_column(ForeignKey("founders.id"), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    deck_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    claims_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    axes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    diligence_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    memo_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    adversarial_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_brief_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    thesis_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    founder: Mapped[Founder] = relationship(back_populates="applications")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    founder_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    application_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
