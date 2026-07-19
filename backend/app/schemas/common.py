from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RiskAppetite = Literal["low", "medium", "high"]
Origin = Literal["github", "hn", "inbound", "synthetic"]
Trend = Literal["up", "flat", "down"]


class Thesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sectors: list[str]
    stage: str
    geo: list[str]
    check_size: int = Field(default=100_000, ge=100_000, le=100_000)
    risk_appetite: RiskAppetite


class ThesisResponse(BaseModel):
    thesis: Thesis


class ThesisWriteRequest(BaseModel):
    thesis: Thesis


class OkResponse(BaseModel):
    ok: Literal[True] = True


class SignalOut(BaseModel):
    signal_id: str
    ts: datetime
    source: str
    text: str
    url: str | None = None


class ProfileOut(BaseModel):
    founder_id: str
    name: str
    headline: str | None = None
    location: str | None = None
    origin: Origin
    bio: str | None = None


class ScoreHistoryItem(BaseModel):
    ts: datetime
    score: int
    band: int


class DashboardFounder(BaseModel):
    founder_id: str
    name: str
    origin: Origin
    founder_score: int
    band: int
    trend: Trend
    top_signals: list[str]
    has_open_app: bool


class FounderDetailResponse(BaseModel):
    profile: ProfileOut
    signals: list[SignalOut]
    score_history: list[ScoreHistoryItem]
    applications: list[str]
