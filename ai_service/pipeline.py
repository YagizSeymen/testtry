"""Bounded AI stages for the product contract in :mod:`steps.md`.

The backend owns durable state, identity, deterministic scoring, and the human
gate. This module receives immutable snapshots of that state and returns the
small, typed results that the backend persists. Every model stage has a
deterministic fallback so the demo and parallel integration do not depend on an
API key.
"""

from __future__ import annotations

import hashlib
import math
import re
from operator import add
from typing import Annotated, Any, Literal, TypedDict

from .model_router import ModelRouter

try:
    from langgraph.graph import END, START, StateGraph
except ImportError:  # pragma: no cover - used only without optional dependency
    END = START = StateGraph = None


CLAIM_TYPES = {"traction", "team", "market", "product"}
TRENDS = {"up", "flat", "down"}
MARKET_RATINGS = {"bullish", "neutral", "bear"}
IDEA_VERDICTS = {"survives", "pivot", "fails"}
UNTRUSTED_DECK_PREFIXES = (
    "system:",
    "assistant:",
    "developer:",
    "ignore previous",
    "ignore all previous",
    "disregard",
    "skip diligence",
)
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "our",
    "that",
    "the",
    "their",
    "this",
    "to",
    "we",
    "with",
}


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part) for part in parts if part is not None)
    return f"{prefix}_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:10]}"


def _string(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) else default


def _records(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9-]*", text.lower())
        if len(token) > 1 and token not in STOP_WORDS
    }


def _is_untrusted_deck_text(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered.startswith(UNTRUSTED_DECK_PREFIXES) or any(
        phrase in lowered
        for phrase in ("prompt injection", "follow these instructions", "override the system")
    )


def _sentence_like_spans(deck_text: str) -> list[str]:
    spans: list[str] = []
    for chunk in re.split(r"(?<=[.!?])\s+|\n+", deck_text):
        span = chunk.strip()
        if 12 <= len(span) <= 700 and not _is_untrusted_deck_text(span):
            spans.append(span)
    return _dedupe(spans)


def _claim_type(text: str) -> str | None:
    lowered = text.lower()
    if any(word in lowered for word in ("market", "industry", "customer segment", "ai infrastructure", "demand", "buyer", "spend")):
        return "market"
    if any(word in lowered for word in ("product", "platform", "api", "tool", "model", "workflow", "software", "infrastructure", "shipped", "launch")):
        return "product"
    if any(word in lowered for word in ("founder", "co-founder", "cofounder", "ceo", "cto", "team", "engineer", "hackathon", "github")):
        return "team"
    if any(word in lowered for word in ("mrr", "arr", "revenue", "customer", "pilot", "users", "traction", "retention")):
        return "traction"
    return None


def _fallback_founder_name(deck_text: str) -> str:
    patterns = (
        r"(?im)^\s*(?:founder|co-founder|cofounder|ceo|cto)\s*[:\-]\s*([A-Z][A-Za-z .'-]{1,80})",
        r"(?i)\b(?:founded|co-founded|cofounded) by\s+([A-Z][A-Za-z .'-]{1,80})",
    )
    for pattern in patterns:
        match = re.search(pattern, deck_text)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip(" .,-")
    return "Unknown founder"


def _fallback_extract(payload: dict[str, Any]) -> dict[str, Any]:
    company_name = _string(payload.get("company_name"), "Unknown company")
    deck_text = _string(payload.get("deck_text"))
    claims: list[dict[str, Any]] = []
    for index, span in enumerate(_sentence_like_spans(deck_text)):
        claim_type = _claim_type(span)
        if claim_type is None:
            continue
        claims.append(
            {
                "claim_id": _stable_id("clm", company_name, claim_type, span),
                "type": claim_type,
                "text": span,
                "source_span": span,
            }
        )
        if len(claims) == 12:
            break
    return {"founder_name": _fallback_founder_name(deck_text), "claims": claims}


def _normalise_extraction(raw: dict[str, Any], payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    company_name = _string(payload.get("company_name"), "Unknown company")
    deck_text = _string(payload.get("deck_text"))
    valid = True
    claims: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(_records(raw.get("claims"))):
        claim_type = _string(item.get("type"))
        text = _string(item.get("text"))
        span_value = item.get("source_span")
        span = _string(span_value) if isinstance(span_value, str) else ""
        if claim_type not in CLAIM_TYPES or not text:
            valid = False
            continue
        if not span or span not in deck_text or _is_untrusted_deck_text(span):
            valid = False
            span = ""
        key = (claim_type, text.lower())
        if key in seen:
            continue
        seen.add(key)
        claims.append(
            {
                "claim_id": _string(item.get("claim_id")) or _stable_id("clm", company_name, claim_type, text, index),
                "type": claim_type,
                "text": text,
                "source_span": span or None,
            }
        )
    founder_name = _string(raw.get("founder_name")) or _fallback_founder_name(deck_text)
    return {"founder_name": founder_name, "claims": claims}, valid


def extract_application(payload: dict[str, Any]) -> dict[str, Any]:
    """LLM #1 with one span-validation retry; deck text is never executable."""

    if not _string(payload.get("company_name")) or not isinstance(payload.get("deck_text"), str):
        raise ValueError("company_name and deck_text are required.")
    router = ModelRouter()
    raw = router.run("extract", payload, _fallback_extract)
    result, valid = _normalise_extraction(raw, payload)
    if valid:
        return result

    # The contract permits exactly one retry. Invalid rows remain null-span if
    # the retry cannot provide an exact quote from the original deck.
    retry_payload = {**payload, "span_retry": True, "previous_result": raw}
    retry_raw = router.run("extract", retry_payload, _fallback_extract)
    retry_result, _ = _normalise_extraction(retry_raw, payload)
    return retry_result


def _fallback_query(payload: dict[str, Any]) -> dict[str, Any]:
    query = _string(payload.get("q")).lower()
    thesis = payload.get("thesis") if isinstance(payload.get("thesis"), dict) else {}
    sectors = [str(item) for item in thesis.get("sectors", []) if str(item).strip()]
    if ("ai infra" in query or "ai infrastructure" in query) and not any("ai infrastructure" in item.lower() for item in sectors):
        sectors.append("AI infrastructure")
    geos = [str(item) for item in thesis.get("geo", []) if str(item).strip() and item.lower() in query]
    if "europe" in query and not any("europe" in item.lower() for item in geos):
        geos.append("Europe")
    shipped = re.search(r"(?:last|within)\s+(\d+)\s+days?", query)
    return {
        "technical_founder": True if "technical founder" in query or "technical" in query else None,
        "sectors": _dedupe(sectors),
        "geos": _dedupe(geos),
        "shipped_within_days": int(shipped.group(1)) if shipped else (30 if "recent" in query else None),
        "prior_vc": False if any(term in query for term in ("no prior vc", "without vc", "no vc funding", "unfunded")) else None,
    }


def parse_query(payload: dict[str, Any]) -> dict[str, Any]:
    if not _string(payload.get("q")) or not isinstance(payload.get("thesis"), dict):
        raise ValueError("q and thesis are required.")
    raw = ModelRouter().run("query", payload, _fallback_query)
    fallback = _fallback_query(payload)
    return {
        "technical_founder": raw.get("technical_founder") if isinstance(raw.get("technical_founder"), bool) else fallback["technical_founder"],
        "sectors": _dedupe([_string(item) for item in raw.get("sectors", [])]) if isinstance(raw.get("sectors"), list) else fallback["sectors"],
        "geos": _dedupe([_string(item) for item in raw.get("geos", [])]) if isinstance(raw.get("geos"), list) else fallback["geos"],
        "shipped_within_days": raw.get("shipped_within_days") if isinstance(raw.get("shipped_within_days"), int) and raw["shipped_within_days"] >= 0 else fallback["shipped_within_days"],
        "prior_vc": raw.get("prior_vc") if isinstance(raw.get("prior_vc"), bool) else fallback["prior_vc"],
    }


def _signal_text(signal: dict[str, Any]) -> str:
    return _string(signal.get("text"))


def _is_contrary(claim: dict[str, Any], signal: dict[str, Any]) -> bool:
    claim_text = _string(claim.get("text")).lower()
    signal_text = _signal_text(signal).lower()
    positive_revenue = claim.get("type") == "traction" and any(
        term in claim_text for term in ("mrr", "arr", "revenue", "paid customer", "customers")
    )
    negative_revenue = any(term in signal_text for term in ("pre-revenue", "no revenue", "zero revenue", "not monetized"))
    if positive_revenue and negative_revenue:
        return True
    claim_positive = any(term in claim_text for term in ("shipped", "launched", "live", "signed", "won"))
    signal_negative = any(term in signal_text for term in ("not shipped", "not launched", "no customers", "shut down"))
    return claim_positive and signal_negative


def _supports(claim: dict[str, Any], signal: dict[str, Any]) -> bool:
    if _is_contrary(claim, signal):
        return False
    claim_tokens = _tokens(_string(claim.get("text")))
    signal_tokens = _tokens(_signal_text(signal))
    overlap = claim_tokens & signal_tokens
    if len(overlap) >= 2:
        return True
    if claim.get("type") == "market" and {"ai", "infrastructure"} <= overlap:
        return True
    return False


def _fallback_screen(payload: dict[str, Any]) -> dict[str, Any]:
    claims = _records(payload.get("claims"))
    signals = _records(payload.get("signals"))
    thesis = payload.get("thesis") if isinstance(payload.get("thesis"), dict) else {}
    founder_score = max(0.0, min(100.0, float(payload.get("founder_score") or 0)))
    trend = _string(payload.get("trend"), "flat")
    if trend not in TRENDS:
        trend = "flat"
    corpus = " ".join([_string(item.get("text")) for item in claims + signals]).lower()
    thesis_terms = _tokens(" ".join(str(item) for item in thesis.get("sectors", [])))
    corpus_terms = _tokens(corpus)
    thesis_matches = len(thesis_terms & corpus_terms)
    product_present = any(item.get("type") == "product" for item in claims)
    market_present = any(item.get("type") == "market" for item in claims)
    founder_axis = max(0, min(10, int(round(4 + founder_score / 20))))
    market_rating = "bullish" if thesis_matches >= 1 and market_present else "neutral"
    if thesis_terms and not thesis_matches:
        market_rating = "bear"
    idea_verdict = "survives" if product_present and market_present else "pivot" if product_present else "fails"
    return {
        "founder": {
            "score": founder_axis,
            "trend": trend,
            "rationale": f"Founder Score is {founder_score:.0f} with a {int(payload.get('band') or 30)} point uncertainty band; the trend is deterministic.",
        },
        "market": {
            "rating": market_rating,
            "rationale": "The thesis and supplied market evidence overlap." if market_rating == "bullish" else "Current Memory gives limited thesis-specific market evidence.",
        },
        "idea_vs_market": {
            "verdict": idea_verdict,
            "rationale": "The supplied claims cover both product and target market." if idea_verdict == "survives" else "More product-market evidence is required before the thesis survives screening.",
        },
    }


def _normalise_axes(raw: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    fallback = _fallback_screen(payload)
    raw = raw.get("axes") if isinstance(raw.get("axes"), dict) else raw
    founder = raw.get("founder") if isinstance(raw.get("founder"), dict) else {}
    market = raw.get("market") if isinstance(raw.get("market"), dict) else {}
    idea = raw.get("idea_vs_market") if isinstance(raw.get("idea_vs_market"), dict) else {}
    score = founder.get("score")
    if not isinstance(score, (int, float)):
        score = fallback["founder"]["score"]
    trend = _string(payload.get("trend"), "flat")
    return {
        "founder": {
            "score": max(0, min(10, score)),
            "trend": trend if trend in TRENDS else "flat",
            "rationale": _string(founder.get("rationale")) or fallback["founder"]["rationale"],
        },
        "market": {
            "rating": _string(market.get("rating")) if _string(market.get("rating")) in MARKET_RATINGS else fallback["market"]["rating"],
            "rationale": _string(market.get("rationale")) or fallback["market"]["rationale"],
        },
        "idea_vs_market": {
            "verdict": _string(idea.get("verdict")) if _string(idea.get("verdict")) in IDEA_VERDICTS else fallback["idea_vs_market"]["verdict"],
            "rationale": _string(idea.get("rationale")) or fallback["idea_vs_market"]["rationale"],
        },
    }


def screen_application(payload: dict[str, Any]) -> dict[str, Any]:
    required = ("company_name", "claims", "signals", "founder_score", "band", "trend", "thesis")
    if any(key not in payload for key in required):
        raise ValueError("screen requires company_name, claims, signals, Founder Score, trend, and thesis.")
    raw = ModelRouter().run("screen", payload, _fallback_screen)
    return _normalise_axes(raw, payload)


def _fallback_diligence(payload: dict[str, Any]) -> dict[str, Any]:
    claims = _records(payload.get("claims"))
    signals = _records(payload.get("signals"))
    results: list[dict[str, Any]] = []
    for claim in claims:
        claim_id = _string(claim.get("claim_id"))
        if not claim_id:
            continue
        contrary = [signal for signal in signals if _is_contrary(claim, signal) and _string(signal.get("signal_id"))]
        support = [signal for signal in signals if _supports(claim, signal) and _string(signal.get("signal_id"))]
        if not _string(claim.get("source_span")):
            verdict, evidence, note = "unverifiable", [], "Claim lacks an exact source span in the submitted deck."
        elif contrary:
            verdict = "contradicted"
            evidence = _dedupe([_string(signal.get("signal_id")) for signal in contrary])
            note = "A resolved Memory signal directly contradicts this claim."
        elif support:
            verdict = "supported"
            evidence = _dedupe([_string(signal.get("signal_id")) for signal in support])
            note = "Resolved Memory signals support this claim."
        else:
            verdict, evidence, note = "unverifiable", [], "No resolved Memory signal supports or contradicts this claim."
        results.append({"claim_id": claim_id, "verdict": verdict, "evidence": evidence, "note": note})
    return {"claims": results, "gaps": ["Cap table: not disclosed"]}


def _normalise_diligence(raw: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    fallback = _fallback_diligence(payload)
    claims = { _string(item.get("claim_id")): item for item in _records(payload.get("claims")) if _string(item.get("claim_id")) }
    signals = { _string(item.get("signal_id")): item for item in _records(payload.get("signals")) if _string(item.get("signal_id")) }
    raw_by_id = { _string(item.get("claim_id")): item for item in _records(raw.get("claims")) }
    fallback_by_id = {item["claim_id"]: item for item in fallback["claims"]}
    normalised: list[dict[str, Any]] = []
    for claim_id, claim in claims.items():
        candidate = raw_by_id.get(claim_id, fallback_by_id.get(claim_id, {}))
        verdict = _string(candidate.get("verdict"))
        evidence = _dedupe([_string(value) for value in candidate.get("evidence", [])]) if isinstance(candidate.get("evidence"), list) else []
        evidence = [signal_id for signal_id in evidence if signal_id in signals]
        if not _string(claim.get("source_span")):
            verdict, evidence = "unverifiable", []
        elif verdict == "contradicted" and not any(_is_contrary(claim, signals[signal_id]) for signal_id in evidence):
            verdict, evidence = "unverifiable", []
        elif verdict == "supported" and not evidence:
            verdict = "unverifiable"
        elif verdict not in {"supported", "contradicted", "unverifiable"}:
            fallback_item = fallback_by_id.get(claim_id, {})
            verdict, evidence = fallback_item.get("verdict", "unverifiable"), fallback_item.get("evidence", [])
        if verdict == "supported":
            trust = "high" if len(evidence) >= 2 else "med"
        else:
            trust = "low"
        normalised.append(
            {
                "claim_id": claim_id,
                "verdict": verdict,
                "trust": trust,
                "evidence": evidence,
                "note": _string(candidate.get("note")) or _string(fallback_by_id.get(claim_id, {}).get("note"), "Evidence was not resolved."),
            }
        )
    gaps = _dedupe([_string(item) for item in raw.get("gaps", [])]) if isinstance(raw.get("gaps"), list) else []
    if "Cap table: not disclosed" not in gaps:
        gaps.append("Cap table: not disclosed")
    return {"claims": normalised, "gaps": gaps}


def diligence_claims(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload.get("claims"), list) or not isinstance(payload.get("signals"), list):
        raise ValueError("diligence requires claims and signals arrays.")
    raw = ModelRouter().run("diligence", payload, _fallback_diligence)
    return _normalise_diligence(raw, payload)


def _committed_claim_ids(claims: list[dict[str, Any]], diligence: dict[str, Any]) -> list[str]:
    valid_spans = { _string(item.get("claim_id")) for item in claims if _string(item.get("claim_id")) and _string(item.get("source_span")) }
    return _dedupe(
        [
            _string(item.get("claim_id"))
            for item in _records(diligence.get("claims"))
            if item.get("verdict") == "supported" and _string(item.get("claim_id")) in valid_spans
        ]
    )


def _fallback_memo(payload: dict[str, Any]) -> dict[str, Any]:
    company_name = _string(payload.get("company_name"), "This company")
    claims = _records(payload.get("claims"))
    diligence = payload.get("diligence") if isinstance(payload.get("diligence"), dict) else {}
    axes = payload.get("axes") if isinstance(payload.get("axes"), dict) else {}
    committed_ids = _committed_claim_ids(claims, diligence)
    claim_by_id = { _string(item.get("claim_id")): item for item in claims }
    committed_text = [claim_by_id[claim_id].get("text", "") for claim_id in committed_ids if claim_id in claim_by_id]
    gaps = [str(item) for item in diligence.get("gaps", []) if str(item).strip()]
    can_invest = bool(committed_ids) and axes.get("market", {}).get("rating") != "bear" and axes.get("idea_vs_market", {}).get("verdict") != "fails"
    return {
        "memo_id": _stable_id("memo", company_name, *committed_ids),
        "sections": {
            "snapshot": f"{company_name} is assessed from submitted claims and resolved Memory evidence.",
            "hypotheses": "Supported thesis: " + ("; ".join(committed_text) if committed_text else "no supported claim is committed."),
            "swot": "Strength: resolved evidence. Weakness: evidence gaps. Opportunity: thesis alignment. Threat: unresolved or contradicted claims.",
            "problem_product": "Product and market judgment: " + _string(axes.get("idea_vs_market", {}).get("rationale"), "not established."),
            "traction_kpis": "Gaps: " + ("; ".join(gaps) if gaps else "none recorded.")
        },
        "recommendation": {
            "invest": can_invest,
            "amount": 100000,
            "rationale": "Recommendation uses only supported claims with exact deck spans." if can_invest else "Do not invest until at least one claim with an exact deck span is supported.",
            "based_on": committed_ids,
        },
    }


def _normalise_memo(raw: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    fallback = _fallback_memo(payload)
    raw = raw.get("memo") if isinstance(raw.get("memo"), dict) else raw
    sections = raw.get("sections") if isinstance(raw.get("sections"), dict) else {}
    required_sections = ("snapshot", "hypotheses", "swot", "problem_product", "traction_kpis")
    result_sections = {
        key: _string(sections.get(key)) or fallback["sections"][key]
        for key in required_sections
    }
    committed = _committed_claim_ids(_records(payload.get("claims")), payload.get("diligence") if isinstance(payload.get("diligence"), dict) else {})
    recommendation = raw.get("recommendation") if isinstance(raw.get("recommendation"), dict) else {}
    requested = [value for value in recommendation.get("based_on", []) if isinstance(value, str)] if isinstance(recommendation.get("based_on"), list) else []
    based_on = [claim_id for claim_id in _dedupe(requested) if claim_id in committed]
    if not requested:
        based_on = committed
    invest = bool(based_on) and bool(recommendation.get("invest", fallback["recommendation"]["invest"]))
    if not based_on:
        invest = False
    return {
        "memo_id": _string(raw.get("memo_id")) or fallback["memo_id"],
        "sections": result_sections,
        "recommendation": {
            "invest": invest,
            "amount": 100000,
            "rationale": _string(recommendation.get("rationale")) or fallback["recommendation"]["rationale"],
            "based_on": based_on,
        },
    }


def write_memo(payload: dict[str, Any]) -> dict[str, Any]:
    if not _string(payload.get("company_name")) or not isinstance(payload.get("claims"), list):
        raise ValueError("memo requires company_name, claims, diligence, and axes.")
    if not isinstance(payload.get("diligence"), dict) or not isinstance(payload.get("axes"), dict):
        raise ValueError("memo requires company_name, claims, diligence, and axes.")
    raw = ModelRouter().run("memo", payload, _fallback_memo)
    return _normalise_memo(raw, payload)


def weakest_axis(axes: dict[str, Any]) -> tuple[str, str]:
    founder = axes.get("founder") if isinstance(axes.get("founder"), dict) else {}
    market = axes.get("market") if isinstance(axes.get("market"), dict) else {}
    idea = axes.get("idea_vs_market") if isinstance(axes.get("idea_vs_market"), dict) else {}
    founder_score = float(founder.get("score") or 0)
    founder_rank = 0 if founder_score <= 3 else 1 if founder_score <= 7 else 2
    market_rank = {"bear": 0, "neutral": 1, "bullish": 2}.get(_string(market.get("rating")), 0)
    idea_rank = {"fails": 0, "pivot": 1, "survives": 2}.get(_string(idea.get("verdict")), 0)
    choices = [
        (founder_rank, "founder", "Founder-Risk Partner"),
        (market_rank, "market", "Market-Skeptic Partner"),
        (idea_rank, "idea_vs_market", "Product-Market-Fit Skeptic"),
    ]
    _, axis, persona = min(choices, key=lambda choice: choice[0])
    return axis, persona


def _fallback_adversary(payload: dict[str, Any]) -> dict[str, Any]:
    memo = payload.get("memo") if isinstance(payload.get("memo"), dict) else {}
    axes = payload.get("axes") if isinstance(payload.get("axes"), dict) else {}
    claims = _records(payload.get("claims"))
    signals = _records(payload.get("signals"))
    _, persona = weakest_axis(axes)
    claim_ids = { _string(item.get("claim_id")) for item in claims }
    based_on = [claim_id for claim_id in memo.get("recommendation", {}).get("based_on", []) if claim_id in claim_ids]
    targets = based_on or sorted(claim_ids)
    objections: list[dict[str, Any]] = []
    if targets and signals:
        signal = next((item for item in signals if _string(item.get("signal_id"))), None)
        if signal is not None:
            signal_id = _string(signal.get("signal_id"))
            objections.append(
                {
                    "text": f"Counter-case: Memory contains this evidence requiring scrutiny before approval: {_signal_text(signal)}",
                    "targets": targets[:1],
                    "evidence": [signal_id],
                    "label": "evidence-backed",
                    "verification": "unverified",
                }
            )
    if targets:
        objections.append(
            {
                "text": "Speculation: the current evidence may not persist at the scale implied by the memo.",
                "targets": targets[:1],
                "evidence": None,
                "label": "speculation",
                "verification": "n/a",
            }
        )
    return {"persona": persona, "objections": objections}


def _normalise_adversarial(raw: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    fallback = _fallback_adversary(payload)
    raw = raw.get("adversarial") if isinstance(raw.get("adversarial"), dict) else raw
    axes = payload.get("axes") if isinstance(payload.get("axes"), dict) else {}
    _, persona = weakest_axis(axes)
    valid_claim_ids = { _string(item.get("claim_id")) for item in _records(payload.get("claims")) }
    valid_signal_ids = { _string(item.get("signal_id")) for item in _records(payload.get("signals")) }
    objections: list[dict[str, Any]] = []
    for item in _records(raw.get("objections")):
        text = _string(item.get("text"))
        targets = [value for value in _dedupe([_string(value) for value in item.get("targets", [])]) if value in valid_claim_ids] if isinstance(item.get("targets"), list) else []
        evidence = [value for value in _dedupe([_string(value) for value in item.get("evidence", [])]) if value in valid_signal_ids] if isinstance(item.get("evidence"), list) else []
        if not text or not targets:
            continue
        objections.append(
            {
                "text": text,
                "targets": targets,
                "evidence": evidence or None,
                "label": "evidence-backed" if evidence else "speculation",
                "verification": "unverified" if evidence else "n/a",
            }
        )
    return {"persona": persona, "objections": objections or fallback["objections"]}


def write_adversary(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload.get("memo"), dict) or not isinstance(payload.get("axes"), dict):
        raise ValueError("adversary requires memo, axes, claims, and signals.")
    raw = ModelRouter().run("adversary", payload, _fallback_adversary)
    return _normalise_adversarial(raw, payload)


def _relevant_to_objection(objection: dict[str, Any], signal: dict[str, Any]) -> bool:
    return bool(_tokens(_string(objection.get("text"))) & _tokens(_signal_text(signal)))


def _fallback_verify_adversary(payload: dict[str, Any]) -> dict[str, Any]:
    adversarial = payload.get("adversarial") if isinstance(payload.get("adversarial"), dict) else {}
    signal_map = { _string(item.get("signal_id")): item for item in _records(payload.get("signals")) if _string(item.get("signal_id")) }
    objections: list[dict[str, Any]] = []
    for objection in _records(adversarial.get("objections")):
        evidence = [value for value in objection.get("evidence", []) if isinstance(value, str) and value in signal_map] if isinstance(objection.get("evidence"), list) else []
        verified = bool(evidence) and any(_relevant_to_objection(objection, signal_map[value]) for value in evidence)
        objections.append({**objection, "evidence": evidence or None, "label": "evidence-backed" if evidence else "speculation", "verification": "verified" if verified else "unverified" if evidence else "n/a"})
    return {"persona": _string(adversarial.get("persona")), "objections": objections}


def verify_adversary(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload.get("adversarial"), dict) or not isinstance(payload.get("signals"), list):
        raise ValueError("adversarial, claims, and signals are required for batch verification.")
    raw = ModelRouter().run("verify_adversary", payload, _fallback_verify_adversary)
    baseline = _fallback_verify_adversary(payload)
    raw = raw.get("adversarial") if isinstance(raw.get("adversarial"), dict) else raw
    raw_objections = _records(raw.get("objections"))
    verified_objections: list[dict[str, Any]] = []
    for index, baseline_objection in enumerate(baseline["objections"]):
        candidate = raw_objections[index] if index < len(raw_objections) else {}
        verification = _string(candidate.get("verification"))
        if baseline_objection["verification"] == "n/a":
            verification = "n/a"
        elif verification not in {"verified", "unverified"}:
            verification = baseline_objection["verification"]
        verified_objections.append({**baseline_objection, "verification": verification})
    return {"persona": baseline["persona"], "objections": verified_objections}


class ApplicationState(TypedDict, total=False):
    company_name: str
    deck_text: str
    signals: list[dict[str, Any]]
    founder_score: float
    band: int
    trend: str
    thesis: dict[str, Any]
    include_adversary: bool
    founder_name: str
    claims: list[dict[str, Any]]
    axes: dict[str, Any]
    diligence: dict[str, Any]
    memo: dict[str, Any]
    adversarial: dict[str, Any] | None
    trace: Annotated[list[str], add]


def _extract_node(state: ApplicationState) -> ApplicationState:
    result = extract_application({"company_name": state["company_name"], "deck_text": state["deck_text"]})
    return {"founder_name": result["founder_name"], "claims": result["claims"], "trace": ["extract:luna"]}


def _screen_node(state: ApplicationState) -> ApplicationState:
    axes = screen_application({key: state[key] for key in ("company_name", "claims", "signals", "founder_score", "band", "trend", "thesis")})
    return {"axes": axes, "trace": ["screen:terra"]}


def _diligence_node(state: ApplicationState) -> ApplicationState:
    diligence = diligence_claims({"claims": state["claims"], "signals": state["signals"]})
    return {"diligence": diligence, "trace": ["diligence:terra"]}


def _memo_node(state: ApplicationState) -> ApplicationState:
    memo = write_memo({key: state[key] for key in ("company_name", "claims", "diligence", "axes")})
    return {"memo": memo, "trace": ["memo:terra"]}


def _adversary_node(state: ApplicationState) -> ApplicationState:
    adversarial = write_adversary({key: state[key] for key in ("memo", "axes", "claims", "signals")})
    return {"adversarial": adversarial, "trace": ["adversary:terra:one-pass"]}


def _verify_node(state: ApplicationState) -> ApplicationState:
    adversarial = verify_adversary({"adversarial": state["adversarial"], "claims": state["claims"], "signals": state["signals"]})
    return {"adversarial": adversarial, "trace": ["verify_adversary:terra:one-batch"]}


def _after_memo(state: ApplicationState) -> Literal["adversary", "end"]:
    return "adversary" if state.get("include_adversary") else "end"


def create_application_workflow():
    """Fixed LangGraph DAG; the human decision and Decision Brief are outside it."""

    if StateGraph is None:
        raise RuntimeError("LangGraph is not installed. Run: python3 -m pip install -r ai_service/requirements.txt")
    graph = StateGraph(ApplicationState)
    graph.add_node("extract", _extract_node)
    graph.add_node("screen", _screen_node)
    graph.add_node("diligence", _diligence_node)
    graph.add_node("memo", _memo_node)
    graph.add_node("adversary", _adversary_node)
    graph.add_node("verify_adversary", _verify_node)
    graph.add_edge(START, "extract")
    graph.add_edge("extract", "screen")
    graph.add_edge("screen", "diligence")
    graph.add_edge("diligence", "memo")
    graph.add_conditional_edges("memo", _after_memo, {"adversary": "adversary", "end": END})
    graph.add_edge("adversary", "verify_adversary")
    graph.add_edge("verify_adversary", END)
    return graph.compile()


def _run_application_fallback(state: ApplicationState) -> ApplicationState:
    result: ApplicationState = dict(state)
    for node in (_extract_node, _screen_node, _diligence_node, _memo_node):
        update = node(result)
        result.update({key: value for key, value in update.items() if key != "trace"})
        result["trace"] = [*result.get("trace", []), *update.get("trace", [])]
    if result.get("include_adversary"):
        for node in (_adversary_node, _verify_node):
            update = node(result)
            result.update({key: value for key, value in update.items() if key != "trace"})
            result["trace"] = [*result.get("trace", []), *update.get("trace", [])]
    else:
        result["adversarial"] = None
    return result


def run_application_pipeline(payload: dict[str, Any]) -> dict[str, Any]:
    required = ("company_name", "deck_text", "signals", "founder_score", "band", "trend", "thesis", "include_adversary")
    if any(key not in payload for key in required):
        raise ValueError("application/run requires every AIApplicationRunRequest field.")
    state: ApplicationState = {
        "company_name": _string(payload["company_name"]),
        "deck_text": _string(payload["deck_text"]),
        "signals": _records(payload["signals"]),
        "founder_score": float(payload["founder_score"]),
        "band": int(payload["band"]),
        "trend": _string(payload["trend"]),
        "thesis": payload["thesis"] if isinstance(payload["thesis"], dict) else {},
        "include_adversary": bool(payload["include_adversary"]),
        "trace": [],
    }
    result = create_application_workflow().invoke(state) if StateGraph is not None else _run_application_fallback(state)
    return {
        "founder_name": result["founder_name"],
        "claims": result["claims"],
        "axes": result["axes"],
        "diligence": result["diligence"],
        "memo": result["memo"],
        "adversarial": result.get("adversarial"),
        "trace": result.get("trace", []),
    }


def endpoint_extract(payload: dict[str, Any]) -> dict[str, Any]:
    return extract_application(payload)


def endpoint_query(payload: dict[str, Any]) -> dict[str, Any]:
    return parse_query(payload)


def endpoint_screen(payload: dict[str, Any]) -> dict[str, Any]:
    return screen_application(payload)


def endpoint_diligence(payload: dict[str, Any]) -> dict[str, Any]:
    return diligence_claims(payload)


def endpoint_memo(payload: dict[str, Any]) -> dict[str, Any]:
    return write_memo(payload)


def endpoint_adversary(payload: dict[str, Any]) -> dict[str, Any]:
    return write_adversary(payload)


def endpoint_verify_adversary(payload: dict[str, Any]) -> dict[str, Any]:
    return verify_adversary(payload)


def endpoint_application_run(payload: dict[str, Any]) -> dict[str, Any]:
    return run_application_pipeline(payload)
