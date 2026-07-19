from __future__ import annotations

from typing import Literal


Trust = Literal["high", "med", "low"]
Verdict = Literal["supported", "contradicted", "unverifiable"]


def map_trust(verdict: Verdict, evidence_count: int) -> Trust:
    """Deterministic trust mapping after evidence ID resolution (steps.md §4)."""
    if verdict == "supported":
        if evidence_count >= 2:
            return "high"
        if evidence_count == 1:
            return "med"
        return "low"
    return "low"


def normalize_diligence_row(
    *,
    claim_id: str,
    verdict: str,
    evidence_ids: list[str],
    valid_signal_ids: set[str],
    source_span: str | None,
    note: str,
) -> dict:
    """Backend post-processing for diligence rows."""
    resolved_raw = [eid for eid in evidence_ids if eid in valid_signal_ids]
    resolved: list[str] = []
    seen: set[str] = set()
    for eid in resolved_raw:
        if eid not in seen:
            seen.add(eid)
            resolved.append(eid)

    if not source_span:
        verdict_out: Verdict = "unverifiable"
        resolved = []
    elif verdict == "contradicted" and not resolved:
        verdict_out = "unverifiable"
    elif verdict == "supported" and not resolved:
        verdict_out = "unverifiable"
    elif verdict in {"supported", "contradicted", "unverifiable"}:
        verdict_out = verdict  # type: ignore[assignment]
    else:
        verdict_out = "unverifiable"
        resolved = []

    if verdict_out == "supported" and not resolved:
        verdict_out = "unverifiable"

    return {
        "claim_id": claim_id,
        "verdict": verdict_out,
        "trust": map_trust(verdict_out, len(resolved)),
        "evidence": resolved,
        "note": note,
    }


def guard_memo_recommendation(
    *,
    based_on: list[str],
    claims: list[dict],
    diligence_claims: list[dict],
    invest: bool,
    rationale: str,
) -> dict:
    """Drop null-span / non-supported IDs; force invest:false when none remain."""
    claim_by_id = {c["claim_id"]: c for c in claims}
    supported = {
        d["claim_id"]
        for d in diligence_claims
        if d.get("verdict") == "supported"
    }
    cleaned: list[str] = []
    seen: set[str] = set()
    for claim_id in based_on:
        if claim_id in seen:
            continue
        claim = claim_by_id.get(claim_id)
        if claim is None or not claim.get("source_span"):
            continue
        if claim_id not in supported:
            continue
        seen.add(claim_id)
        cleaned.append(claim_id)

    return {
        "invest": bool(invest) and bool(cleaned),
        "amount": 100_000,
        "rationale": rationale,
        "based_on": cleaned,
    }
