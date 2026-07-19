from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ClaimType = Literal["traction", "team", "market", "product"]
Trend = Literal["up", "flat", "down"]
MarketRating = Literal["bullish", "neutral", "bear"]
IdeaVerdict = Literal["survives", "pivot", "fails"]
ClaimVerdict = Literal["supported", "contradicted", "unverifiable"]
Trust = Literal["high", "med", "low"]


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    type: ClaimType
    text: str
    source_span: str | None = None


class FounderAxis(BaseModel):
    score: float
    trend: Trend
    rationale: str


class MarketAxis(BaseModel):
    rating: MarketRating
    rationale: str


class IdeaAxis(BaseModel):
    verdict: IdeaVerdict
    rationale: str


class Axes(BaseModel):
    founder: FounderAxis
    market: MarketAxis
    idea_vs_market: IdeaAxis


class DiligenceClaim(BaseModel):
    claim_id: str
    verdict: ClaimVerdict
    trust: Trust
    evidence: list[str]
    note: str


class Diligence(BaseModel):
    claims: list[DiligenceClaim]
    gaps: list[str]


class Recommendation(BaseModel):
    invest: bool
    amount: int = Field(default=100_000, ge=100_000, le=100_000)
    rationale: str
    based_on: list[str]


class MemoSections(BaseModel):
    snapshot: str
    hypotheses: str
    swot: str
    problem_product: str
    traction_kpis: str


class Memo(BaseModel):
    memo_id: str
    sections: MemoSections
    recommendation: Recommendation


class ApplicationCreateRequest(BaseModel):
    company_name: str
    deck_text: str


class ApplicationCreateResponse(BaseModel):
    application_id: str
    founder_id: str
    claims: list[Claim]


class ApplicationAggregate(BaseModel):
    application_id: str
    founder_id: str
    company_name: str
    status: Literal["open", "approved", "rejected"]
    claims: list[Claim]
    axes: Axes | None = None
    diligence: Diligence | None = None
    memo: Memo | None = None
    adversarial: dict[str, Any] | None = None
    decision_brief: dict[str, Any] | None = None
    evidence: list[dict[str, Any]]
