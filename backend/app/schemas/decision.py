from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.application import Recommendation


class DecisionQueueItem(BaseModel):
    application_id: str
    company: str
    recommendation: Recommendation
    memo_id: str


class DecideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["approve", "reject"]
    approver: str = Field(min_length=1)


class DecideResponse(BaseModel):
    status: Literal["approved", "rejected"]
    audit_id: str


class AuditEventOut(BaseModel):
    ts: datetime
    stage: str
    actor: str
    action: str
    detail: str


class FunnelMetrics(BaseModel):
    sourced: int
    screened: int
    diligenced: int
    decided: int


class MetricsResponse(BaseModel):
    signal_to_decision_min: float | None
    funnel: FunnelMetrics
