"""Core AI-service pipeline logic for The VC Brain.

This module intentionally has no third-party dependencies. Each function maps
to one public `/v1/ai/*` endpoint and returns JSON-serializable dictionaries
matching `api-contract.json`.
"""

from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse


SCREENING_AXES = [
    "founder",
    "market",
    "product",
    "traction",
    "business_model",
    "fundraising",
    "risk",
]

TIE_BREAKER_ORDER = [
    "risk",
    "founder",
    "traction",
    "market",
    "product",
    "business_model",
    "fundraising",
]

EVIDENCE_TYPES = [
    "company",
    "founder",
    "market",
    "product",
    "traction",
    "competition",
    "business_model",
    "fundraising",
    "risk",
    "unknown",
]

TYPE_KEYWORDS = {
    "founder": [
        "founder",
        "co-founder",
        "ceo",
        "cto",
        "team",
        "linkedin",
        "previous",
        "ex-",
        "built",
        "started",
    ],
    "market": [
        "market",
        "industry",
        "tam",
        "sam",
        "demand",
        "category",
        "sector",
        "billion",
        "growth",
        "customers need",
    ],
    "product": [
        "product",
        "platform",
        "api",
        "model",
        "app",
        "technology",
        "feature",
        "workflow",
        "integration",
        "proprietary",
    ],
    "traction": [
        "revenue",
        "arr",
        "mrr",
        "customer",
        "users",
        "pilot",
        "growth",
        "retention",
        "signed",
        "usage",
        "launched",
    ],
    "competition": [
        "competitor",
        "competition",
        "alternative",
        "incumbent",
        "versus",
        " vs ",
    ],
    "business_model": [
        "pricing",
        "subscription",
        "saas",
        "margin",
        "monetization",
        "unit economics",
        "gross margin",
        "sales motion",
        "business model",
    ],
    "fundraising": [
        "funding",
        "fundraising",
        "raised",
        "seed",
        "series",
        "investor",
        "valuation",
        "round",
        "capital",
    ],
    "risk": [
        "risk",
        "lawsuit",
        "regulated",
        "regulatory",
        "compliance",
        "privacy",
        "security",
        "churn",
        "decline",
        "concern",
        "missing",
        "unknown",
    ],
}

AXIS_EVIDENCE_TYPES = {
    "founder": ["founder"],
    "market": ["market", "competition"],
    "product": ["product", "company"],
    "traction": ["traction"],
    "business_model": ["business_model"],
    "fundraising": ["fundraising"],
    "risk": ["risk"],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts if p is not None)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


def require_object(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Missing object field: {key}")
    return value


def require_list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"Missing list field: {key}")
    return [v for v in value if isinstance(v, dict)]


def deal_id(deal: dict[str, Any]) -> str:
    return str(deal.get("deal_id") or stable_id("deal", company_name(deal)))


def company_name(deal: dict[str, Any]) -> str:
    intake = deal.get("intake") if isinstance(deal.get("intake"), dict) else {}
    return str(intake.get("company_name") or deal.get("company_name") or "Unknown Company").strip()


def company_url(deal: dict[str, Any]) -> str | None:
    intake = deal.get("intake") if isinstance(deal.get("intake"), dict) else {}
    url = intake.get("company_url") or deal.get("company_url")
    return str(url).strip() if url else None


def founder_names(deal: dict[str, Any]) -> list[str]:
    intake = deal.get("intake") if isinstance(deal.get("intake"), dict) else {}
    names = intake.get("founder_names") or []
    return [str(n).strip() for n in names if str(n).strip()]


def short_description(deal: dict[str, Any]) -> str:
    intake = deal.get("intake") if isinstance(deal.get("intake"), dict) else {}
    return str(intake.get("short_description") or "").strip()


def strip_html(text: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def split_sentences(text: str) -> list[str]:
    clean = strip_html(text)
    pieces = re.split(r"(?<=[.!?])\s+|\n+|(?:\s+-\s+)", clean)
    sentences = []
    for piece in pieces:
        normalized = re.sub(r"\s+", " ", piece).strip(" -\t\r\n")
        if 35 <= len(normalized) <= 500:
            sentences.append(normalized)
    return sentences


def tokenize(text: str) -> set[str]:
    stop = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "are",
        "was",
        "were",
        "has",
        "have",
        "into",
        "their",
        "they",
        "its",
        "our",
        "your",
        "about",
    }
    return {w for w in re.findall(r"[a-z0-9][a-z0-9\-]{2,}", text.lower()) if w not in stop}


def classify_evidence_type(sentence: str, deal: dict[str, Any]) -> str:
    lower = f" {sentence.lower()} "
    scores: dict[str, int] = {}
    for evidence_type, keywords in TYPE_KEYWORDS.items():
        scores[evidence_type] = sum(1 for kw in keywords if kw in lower)
    if company_name(deal).lower() in lower and not any(scores.values()):
        return "company"
    best_type, best_score = max(scores.items(), key=lambda item: item[1])
    return best_type if best_score > 0 else "unknown"


def confidence_for(source: dict[str, Any], sentence: str) -> str:
    source_kind = source.get("kind")
    if source_kind in {"company_site", "founder_profile", "investor_page", "product_page"}:
        return "high"
    if re.search(r"\b(arr|revenue|raised|customers|users|signed|pilot)\b", sentence, re.I):
        return "medium"
    return "medium" if len(sentence) > 80 else "low"


def freshness_for(sentence: str) -> str:
    years = [int(y) for y in re.findall(r"\b(20[0-2][0-9])\b", sentence)]
    if not years:
        return "unknown"
    latest = max(years)
    if latest >= 2024:
        return "current"
    if latest <= 2021:
        return "stale"
    return "unknown"


def relevant_sentence(sentence: str, deal: dict[str, Any]) -> bool:
    lower = sentence.lower()
    if company_name(deal).lower() in lower:
        return True
    if any(name.lower() in lower for name in founder_names(deal)):
        return True
    return any(kw in lower for words in TYPE_KEYWORDS.values() for kw in words)


def endpoint_research_plan(payload: dict[str, Any]) -> dict[str, Any]:
    deal = require_object(payload, "deal")
    name = company_name(deal)
    founders = founder_names(deal)
    url = company_url(deal)

    queries = [
        f"{name} company funding investors",
        f"{name} founders background",
        f"{name} customers traction revenue",
        f"{name} competitors market size",
        f"{name} reviews product launch",
        f"{name} legal regulatory risk",
    ]
    for founder in founders:
        queries.append(f"{founder} founder {name} background")

    target_urls: list[str] = []
    if url:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        base = f"{parsed.scheme}://{parsed.netloc}"
        target_urls.extend([base, f"{base}/about", f"{base}/pricing", f"{base}/customers", f"{base}/blog"])

    return {
        "queries": dedupe(queries),
        "target_urls": dedupe(target_urls),
        "research_priorities": [
            "company",
            "founder",
            "traction",
            "market",
            "competition",
            "business_model",
            "fundraising",
            "risk",
        ],
    }


def endpoint_evidence_extract(payload: dict[str, Any]) -> dict[str, Any]:
    deal = require_object(payload, "deal")
    source = require_object(payload, "source")
    page_text = str(payload.get("page_text") or "")
    source_id = str(source.get("source_id") or stable_id("src", source.get("url"), source.get("title")))
    url = str(source.get("url") or "")
    title = source.get("title")

    candidates = [s for s in split_sentences(page_text) if relevant_sentence(s, deal)]
    if len(candidates) < 3:
        candidates = split_sentences(page_text)[:10]

    evidence = []
    seen_claims: set[str] = set()
    for sentence in candidates[:20]:
        claim = sentence.strip()
        key = claim.lower()
        if key in seen_claims:
            continue
        seen_claims.add(key)
        evidence_type = classify_evidence_type(claim, deal)
        evidence.append(
            {
                "evidence_id": stable_id("ev", deal_id(deal), source_id, claim),
                "deal_id": deal_id(deal),
                "source_id": source_id,
                "source_url": url,
                "source_title": title,
                "claim": claim,
                "quote": claim,
                "evidence_type": evidence_type,
                "confidence": confidence_for(source, claim),
                "freshness": freshness_for(claim),
                "captured_at": now_iso(),
            }
        )
    return {"evidence": evidence}


def endpoint_screen_score(payload: dict[str, Any]) -> dict[str, Any]:
    deal = require_object(payload, "deal")
    evidence = require_list(payload, "evidence")
    by_type = group_evidence_by_type(evidence)
    axis_scores = []

    for axis in SCREENING_AXES:
        related_types = AXIS_EVIDENCE_TYPES[axis]
        related = [item for t in related_types for item in by_type.get(t, [])]
        high_conf = sum(1 for item in related if item.get("confidence") == "high")
        medium_conf = sum(1 for item in related if item.get("confidence") == "medium")

        if axis == "risk":
            risk_items = by_type.get("risk", [])
            score = 75 - min(45, len(risk_items) * 12)
            if not risk_items:
                score = 68
            rationale = (
                "Risk evidence found and should be reviewed."
                if risk_items
                else "No explicit risk evidence found; absence of risk evidence is not proof of low risk."
            )
            related = risk_items
        else:
            score = 35 + min(45, len(related) * 12) + min(20, high_conf * 8 + medium_conf * 4)
            rationale = (
                f"Found {len(related)} relevant evidence records for {axis.replace('_', ' ')}."
                if related
                else f"No direct evidence found for {axis.replace('_', ' ')}."
            )

        axis_scores.append(
            {
                "axis": axis,
                "score": clamp(score),
                "rationale": rationale,
                "evidence_ids": [str(item.get("evidence_id")) for item in related[:6] if item.get("evidence_id")],
                "missing_evidence": missing_evidence_for(axis, related),
            }
        )

    weakest_axis = choose_weakest_axis(axis_scores)
    overall = round(sum(item["score"] for item in axis_scores) / len(axis_scores))
    return {
        "deal_id": deal_id(deal),
        "axis_scores": axis_scores,
        "weakest_axis": weakest_axis,
        "selected_counter_case_lens": weakest_axis,
        "overall_score": overall,
    }


def endpoint_memo_write(payload: dict[str, Any]) -> dict[str, Any]:
    deal = require_object(payload, "deal")
    evidence = require_list(payload, "evidence")
    screening = require_object(payload, "screening")
    name = company_name(deal)
    overall = int(screening.get("overall_score") or 0)
    axis_scores = screening.get("axis_scores") if isinstance(screening.get("axis_scores"), list) else []
    weakest = str(screening.get("weakest_axis") or choose_weakest_axis(axis_scores))
    recommendation = recommendation_for(overall, axis_scores, evidence)
    evidence_ids = [str(item.get("evidence_id")) for item in evidence if item.get("evidence_id")]

    thesis = build_thesis(evidence, axis_scores)
    risks = build_risks(evidence, axis_scores)
    questions = build_diligence_questions(axis_scores, weakest)

    return {
        "memo_id": stable_id("memo", deal_id(deal), overall, len(evidence)),
        "deal_id": deal_id(deal),
        "recommendation": recommendation,
        "summary": (
            f"{name} has an overall screening score of {overall}/100. "
            f"The weakest axis is {weakest.replace('_', ' ')}. "
            "This memo is generated only from Memory evidence and should be reviewed by a human."
        ),
        "investment_thesis": thesis,
        "key_risks": risks,
        "diligence_questions": questions,
        "evidence_ids": evidence_ids[:20],
        "created_at": now_iso(),
    }


def endpoint_adversary_write(payload: dict[str, Any]) -> dict[str, Any]:
    deal = require_object(payload, "deal")
    evidence = require_list(payload, "evidence")
    screening = require_object(payload, "screening")
    memo = require_object(payload, "memo")
    lens = str(screening.get("selected_counter_case_lens") or screening.get("weakest_axis") or "risk")
    weakest_axis = str(screening.get("weakest_axis") or lens)
    axis_scores = screening.get("axis_scores") if isinstance(screening.get("axis_scores"), list) else []
    score_by_axis = {str(item.get("axis")): int(item.get("score") or 0) for item in axis_scores if isinstance(item, dict)}
    relevant = evidence_for_axis(evidence, lens)

    objections = []
    if relevant:
        evidence_ids = [str(item.get("evidence_id")) for item in relevant[:3] if item.get("evidence_id")]
        objections.append(
            objection(
                deal,
                title=f"{lens_title(lens)} may be weaker than the memo implies",
                argument=(
                    f"The memo should be challenged on {lens.replace('_', ' ')} because the strongest "
                    f"available evidence is limited or mixed. The cited records should be checked before approval."
                ),
                severity=severity_for(score_by_axis.get(lens, 50)),
                evidence_ids=evidence_ids,
                is_speculation=False,
            )
        )
    else:
        objections.append(
            objection(
                deal,
                title=f"No direct evidence for {lens_title(lens)}",
                argument=(
                    f"The counter-case is that the memo may overstate {lens.replace('_', ' ')} quality because "
                    "Memory contains no direct evidence for this axis."
                ),
                severity=4,
                evidence_ids=[],
                is_speculation=True,
                speculation_label="Speculation: risk inferred from missing evidence, not a known fact.",
            )
        )

    risk_evidence = evidence_for_axis(evidence, "risk")
    if risk_evidence:
        objections.append(
            objection(
                deal,
                title="Explicit risk evidence may block a fast check",
                argument=(
                    "Memory contains risk-related evidence. A 24-hour investment process should not approve "
                    "until these risk records are reviewed against the memo."
                ),
                severity=5,
                evidence_ids=[str(item.get("evidence_id")) for item in risk_evidence[:3] if item.get("evidence_id")],
                is_speculation=False,
            )
        )

    missing_axes = [item for item in axis_scores if isinstance(item, dict) and item.get("missing_evidence")]
    if missing_axes:
        axis_names = ", ".join(str(item.get("axis")).replace("_", " ") for item in missing_axes[:3])
        objections.append(
            objection(
                deal,
                title="Several screening axes still lack evidence",
                argument=(
                    f"The memo may be premature because these axes have missing evidence: {axis_names}. "
                    "This is a diligence gap rather than a proven negative fact."
                ),
                severity=3,
                evidence_ids=[],
                is_speculation=True,
                speculation_label="Speculation: risk inferred from missing evidence, not a known fact.",
            )
        )

    return {
        "report_id": stable_id("adv", deal_id(deal), memo.get("memo_id"), lens),
        "deal_id": deal_id(deal),
        "memo_id": str(memo.get("memo_id") or ""),
        "counter_case_lens": lens,
        "weakest_axis": weakest_axis,
        "summary": (
            f"Single-pass counter-case focused on {lens.replace('_', ' ')}. "
            "This is not a debate loop; each objection must be verified against Memory."
        ),
        "objections": objections[:5],
        "created_at": now_iso(),
    }


def endpoint_truth_gap_verify(payload: dict[str, Any]) -> dict[str, Any]:
    deal = require_object(payload, "deal")
    evidence = require_list(payload, "evidence")
    adversary_report = require_object(payload, "adversary_report")
    evidence_map = {str(item.get("evidence_id")): item for item in evidence if item.get("evidence_id")}
    checked = []

    for obj in adversary_report.get("objections", []):
        if not isinstance(obj, dict):
            continue
        checked.append(check_objection(obj, evidence_map))

    return {
        "verification_id": stable_id("ver", deal_id(deal), adversary_report.get("report_id"), len(checked)),
        "deal_id": deal_id(deal),
        "adversary_report_id": str(adversary_report.get("report_id") or ""),
        "checked_objections": checked,
        "verified_count": sum(1 for item in checked if item["badge"] == "verified"),
        "unverified_count": sum(1 for item in checked if item["badge"] == "unverified"),
        "speculation_count": sum(1 for item in checked if item["badge"] == "speculation"),
        "created_at": now_iso(),
    }


def endpoint_verdict_brief(payload: dict[str, Any]) -> dict[str, Any]:
    deal = require_object(payload, "deal")
    memo = require_object(payload, "memo")
    verification = require_object(payload, "truth_gap_verification")
    checked = verification.get("checked_objections") if isinstance(verification.get("checked_objections"), list) else []
    verified_ids = [str(item.get("objection_id")) for item in checked if item.get("badge") == "verified"]
    speculation_ids = [str(item.get("objection_id")) for item in checked if item.get("badge") == "speculation"]
    unverified_count = sum(1 for item in checked if item.get("badge") == "unverified")

    if len(verified_ids) >= 2:
        impact = "major"
        signal = "counter_case_serious"
    elif len(verified_ids) == 1 or speculation_ids:
        impact = "minor"
        signal = "needs_human_diligence"
    else:
        impact = "none"
        signal = "memo_still_strong"

    summary = (
        "Non-authoritative reviewer brief: "
        f"{len(verified_ids)} objection(s) are verified, {len(speculation_ids)} are speculation, "
        f"and {unverified_count} are unverified. The human reviewer must make the final decision."
    )

    return {
        "brief_id": stable_id("brief", deal_id(deal), memo.get("memo_id"), verification.get("verification_id")),
        "deal_id": deal_id(deal),
        "memo_id": str(memo.get("memo_id") or ""),
        "verification_id": str(verification.get("verification_id") or ""),
        "decision_impact": impact,
        "signal": signal,
        "summary": summary,
        "strongest_verified_objection_ids": verified_ids[:3],
        "speculation_to_review": speculation_ids[:3],
        "created_at": now_iso(),
    }


def group_evidence_by_type(evidence: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped = {key: [] for key in EVIDENCE_TYPES}
    for item in evidence:
        grouped.setdefault(str(item.get("evidence_type") or "unknown"), []).append(item)
    return grouped


def missing_evidence_for(axis: str, related: list[dict[str, Any]]) -> list[str]:
    if related:
        return []
    prompts = {
        "founder": "Founder background and track record",
        "market": "Market size, timing, and competitor context",
        "product": "Product differentiation and proof",
        "traction": "Customer, usage, revenue, or pilot traction",
        "business_model": "Pricing, margins, sales motion, or unit economics",
        "fundraising": "Round details, prior investors, or valuation fit",
        "risk": "Legal, regulatory, security, or reputational risk review",
    }
    return [prompts.get(axis, f"Evidence for {axis}")]


def choose_weakest_axis(axis_scores: list[dict[str, Any]]) -> str:
    score_by_axis = {str(item.get("axis")): int(item.get("score") or 0) for item in axis_scores if isinstance(item, dict)}
    if not score_by_axis:
        return "risk"
    min_score = min(score_by_axis.values())
    tied = {axis for axis, score in score_by_axis.items() if score == min_score}
    for axis in TIE_BREAKER_ORDER:
        if axis in tied:
            return axis
    return sorted(tied)[0]


def recommendation_for(overall: int, axis_scores: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> str:
    if len(evidence) < 5:
        return "needs_more_research"
    weakest_score = min((int(item.get("score") or 0) for item in axis_scores if isinstance(item, dict)), default=0)
    risk_score = next((int(item.get("score") or 0) for item in axis_scores if item.get("axis") == "risk"), 50)
    if overall >= 72 and weakest_score >= 50 and risk_score >= 45:
        return "approve"
    if overall >= 55:
        return "watchlist"
    if weakest_score < 35 or risk_score < 35:
        return "reject"
    return "needs_more_research"


def build_thesis(evidence: list[dict[str, Any]], axis_scores: list[dict[str, Any]]) -> list[str]:
    strong_axes = [item for item in axis_scores if isinstance(item, dict) and int(item.get("score") or 0) >= 65]
    thesis = []
    for axis in strong_axes[:3]:
        ids = axis.get("evidence_ids") or []
        citation = f" Evidence: {', '.join(ids[:3])}." if ids else ""
        thesis.append(f"{str(axis.get('axis')).replace('_', ' ').title()} screens positively.{citation}")
    if not thesis:
        thesis.append("The investment case is not yet strong enough; more Memory evidence is needed before approval.")
    return thesis


def build_risks(evidence: list[dict[str, Any]], axis_scores: list[dict[str, Any]]) -> list[str]:
    risks = []
    for item in axis_scores:
        if not isinstance(item, dict):
            continue
        if int(item.get("score") or 0) < 50:
            risks.append(f"Weak {str(item.get('axis')).replace('_', ' ')} evidence may undermine the memo.")
    risk_ids = [str(item.get("evidence_id")) for item in evidence if item.get("evidence_type") == "risk" and item.get("evidence_id")]
    if risk_ids:
        risks.append(f"Risk-specific Memory records require review: {', '.join(risk_ids[:4])}.")
    return risks or ["No explicit blocking risk was found, but absence of evidence is not proof of safety."]


def build_diligence_questions(axis_scores: list[dict[str, Any]], weakest: str) -> list[str]:
    questions = [
        f"What primary-source evidence would improve confidence on {weakest.replace('_', ' ')}?",
        "Which claims in the memo rely on company-provided sources rather than independent sources?",
        "What would make this a no-go for a $100K decision within 24 hours?",
    ]
    for item in axis_scores:
        if isinstance(item, dict) and item.get("missing_evidence"):
            questions.append(f"Can we fill the missing evidence for {str(item.get('axis')).replace('_', ' ')}?")
    return dedupe(questions)[:6]


def evidence_for_axis(evidence: list[dict[str, Any]], axis: str) -> list[dict[str, Any]]:
    types = AXIS_EVIDENCE_TYPES.get(axis, [axis])
    return [item for item in evidence if item.get("evidence_type") in types]


def objection(
    deal: dict[str, Any],
    *,
    title: str,
    argument: str,
    severity: int,
    evidence_ids: list[str],
    is_speculation: bool,
    speculation_label: str | None = None,
) -> dict[str, Any]:
    return {
        "objection_id": stable_id("obj", deal_id(deal), title, argument),
        "title": title,
        "argument": argument,
        "severity": max(1, min(5, int(severity))),
        "evidence_ids": evidence_ids,
        "is_speculation": is_speculation,
        "speculation_label": speculation_label,
    }


def check_objection(obj: dict[str, Any], evidence_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    objection_id = str(obj.get("objection_id") or stable_id("obj", obj.get("title"), obj.get("argument")))
    evidence_ids = [str(eid) for eid in obj.get("evidence_ids", []) if eid]
    argument = f"{obj.get('title', '')} {obj.get('argument', '')}"

    if obj.get("is_speculation"):
        return {
            "objection_id": objection_id,
            "badge": "speculation",
            "hallucination_found": False,
            "evidence_relevance": "not_applicable_speculation",
            "contradicted_by_evidence_ids": [],
            "corrected_argument": None,
            "judge_notes": "Objection is explicitly labeled as risk reasoning from missing or weak evidence.",
        }

    missing_ids = [eid for eid in evidence_ids if eid not in evidence_map]
    if missing_ids or not evidence_ids:
        return {
            "objection_id": objection_id,
            "badge": "unverified",
            "hallucination_found": True,
            "evidence_relevance": "does_not_support",
            "contradicted_by_evidence_ids": [],
            "corrected_argument": None,
            "judge_notes": "Objection lacks valid cited evidence IDs in Memory.",
        }

    evidence_text = " ".join(
        f"{evidence_map[eid].get('claim', '')} {evidence_map[eid].get('quote', '')}" for eid in evidence_ids
    )
    overlap = token_overlap(argument, evidence_text)
    if overlap >= 0.18:
        relevance = "supports"
        badge = "verified"
        notes = "Cited Memory records support the objection."
    elif overlap >= 0.08:
        relevance = "partially_supports"
        badge = "verified"
        notes = "Cited Memory records partially support the objection; human should inspect nuance."
    else:
        relevance = "does_not_support"
        badge = "unverified"
        notes = "Cited Memory records do not clearly support the objection."

    return {
        "objection_id": objection_id,
        "badge": badge,
        "hallucination_found": badge == "unverified",
        "evidence_relevance": relevance,
        "contradicted_by_evidence_ids": [],
        "corrected_argument": None if badge == "verified" else "Restate only what the cited evidence directly supports.",
        "judge_notes": notes,
    }


def token_overlap(left: str, right: str) -> float:
    left_tokens = tokenize(left)
    right_tokens = tokenize(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(1, len(left_tokens))


def severity_for(score: int) -> int:
    if score < 35:
        return 5
    if score < 50:
        return 4
    if score < 65:
        return 3
    return 2


def lens_title(lens: str) -> str:
    return lens.replace("_", " ").title()


def clamp(value: int | float) -> int:
    return max(0, min(100, int(round(value))))


def dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
