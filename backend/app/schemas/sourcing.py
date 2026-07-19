from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class QueryFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    technical_founder: bool | None = None
    sectors: list[str] = Field(default_factory=list)
    geos: list[str] = Field(default_factory=list)
    shipped_within_days: int | None = None
    prior_vc: bool | None = None


class QueryMatch(BaseModel):
    founder_id: str
    why_matched: list[str]


class QueryRequest(BaseModel):
    q: str = Field(min_length=1)


class QueryResponse(BaseModel):
    filter: QueryFilter
    results: list[QueryMatch]


class ActivateResponse(BaseModel):
    outreach_draft: str


class ScanRunResponse(BaseModel):
    new_founders: int
    new_signals: int
    cached: Literal[True] = True
