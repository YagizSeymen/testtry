"""Persistent founder-memory and Founder Score support for The VC Brain.

The store is intentionally small and file-backed for the MVP. A production
backend can replace it with a durable database without changing the response
shapes. Scores persist by founder identity and are inputs to opportunities, not
the opportunity score itself.
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import core
from .core import now_iso, stable_id


_LOCK = threading.RLock()
DEFAULT_MEMORY_PATH = "/tmp/vc-brain-founder-memory.json"

SIGNAL_TO_EVIDENCE_TYPE = {
    "europe_location": "founder",
    "technical_founder": "founder",
    "ai_infrastructure": "product",
    "execution": "founder",
    "product_traction": "traction",
    "public_vc_funding": "fundraising",
    "accelerator": "founder",
}


def _normalise_name(name: str) -> str:
    """Match the person-based identity rule in steps.md exactly."""

    return re.sub(r"[\W_]+", "", name.casefold())


def founder_reference(founder_name: str, aliases: list[str] | None = None) -> dict[str, Any]:
    """Return a stable MVP identity reference without claiming strong resolution."""

    normalised = _normalise_name(founder_name)
    if not normalised:
        raise ValueError("founder_name is required.")
    alias_values = [str(alias).strip() for alias in aliases or [] if str(alias).strip()]
    return {
        "founder_id": stable_id("founder", normalised),
        "display_name": founder_name.strip(),
        "aliases": list(dict.fromkeys(alias_values)),
        "resolution_confidence": "low" if not alias_values else "medium",
        "resolution_note": "MVP identity resolution is normalized-name based; merge confirmation is required for ambiguous names.",
    }


def normalise_memory_claim(item: dict[str, Any], founder_id: str) -> dict[str, Any]:
    """Promote candidate or deal evidence into the common Memory claim shape."""

    evidence_id = str(item.get("evidence_id") or stable_id("fev", founder_id, item.get("claim")))
    claim = str(item.get("claim") or item.get("quote") or "Unspecified founder evidence.").strip()
    source_url = str(item.get("source_url") or f"memory://unattributed/{evidence_id}")
    source = {
        "kind": str(item.get("source_kind") or "other"),
        "url": source_url,
        "title": item.get("source_title"),
    }
    default_trust, default_status = core.trust_for(source, claim)
    signal_type = str(item.get("signal_type") or "")
    evidence_type = str(item.get("evidence_type") or SIGNAL_TO_EVIDENCE_TYPE.get(signal_type, "founder"))
    return {
        "evidence_id": evidence_id,
        "deal_id": item.get("deal_id"),
        "candidate_id": item.get("candidate_id"),
        "founder_id": founder_id,
        "source_id": str(item.get("source_id") or stable_id("src", source_url, item.get("source_title"))),
        "source_url": source_url,
        "source_title": item.get("source_title"),
        "source": str(item.get("source") or item.get("source_kind") or "other"),
        "claim": claim,
        "quote": str(item.get("quote") or claim),
        "evidence_type": evidence_type,
        "confidence": str(item.get("confidence") or "low"),
        "trust_score": int(item.get("trust_score") or default_trust),
        "trust_status": str(item.get("trust_status") or default_status),
        "contradicted_by_evidence_ids": list(item.get("contradicted_by_evidence_ids") or []),
        "freshness": str(item.get("freshness") or core.freshness_for(claim)),
        "captured_at": str(item.get("captured_at") or now_iso()),
    }


def _store_path() -> Path:
    return Path(os.getenv("VC_BRAIN_MEMORY_PATH", DEFAULT_MEMORY_PATH))


def _load() -> dict[str, Any]:
    path = _store_path()
    if not path.exists():
        return {"founders": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Founder Memory store contains invalid JSON.") from exc
    return payload if isinstance(payload, dict) and isinstance(payload.get("founders"), dict) else {"founders": {}}


def _save(payload: dict[str, Any]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _signal_matches(evidence: dict[str, Any]) -> set[str]:
    text = " ".join(
        str(evidence.get(key, ""))
        for key in ("claim", "quote", "evidence_type", "source_url", "source_title")
    ).lower()
    matches: set[str] = set()
    if any(term in text for term in ("github", "open source", "repository", "commit", "npm", "pypi")):
        matches.add("technical_execution")
    if any(term in text for term in ("hackathon", "devpost", "winner", "finalist", "mlh")):
        matches.add("competitive_execution")
    if any(term in text for term in ("arxiv", "paper", "publication", "patent", "research")):
        matches.add("technical_depth")
    if any(term in text for term in ("launched", "shipped", "deployed", "built", "released", "production")):
        matches.add("shipping")
    if any(term in text for term in ("customer", "pilot", "revenue", "users", "arr", "retention")):
        matches.add("commercial_execution")
    if any(term in text for term in ("engineer", "developer", "cto", "technical founder")):
        matches.add("technical_background")
    return matches


def _parse_timestamp(value: Any, fallback: datetime) -> datetime:
    if not isinstance(value, str):
        return fallback
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return fallback
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _score(evidence: list[dict[str, Any]], snapshot_at: datetime) -> tuple[int, int, dict[str, int], list[str]]:
    """Implement the deterministic persisted Founder Score from steps.md."""

    by_id = {
        str(item.get("evidence_id")): item
        for item in evidence
        if isinstance(item, dict) and item.get("evidence_id")
    }
    signals = list(by_id.values())
    sources = {
        re.sub(r"\s+", "", str(item.get("source") or item.get("source_kind") or item.get("source_url") or "unknown").casefold())
        for item in signals
    }
    lower_bound = snapshot_at - timedelta(days=30)
    signals_last_30d = sum(
        1
        for item in signals
        if lower_bound <= _parse_timestamp(item.get("captured_at"), snapshot_at) <= snapshot_at
    )
    signals_total = len(signals)
    source_diversity = len(sources)
    score = max(0, min(100, 35 + 8 * source_diversity + 4 * signals_last_30d + 2 * signals_total))
    band = math.floor(max(5, min(30, 60 / math.sqrt(signals_total + 1))))
    inputs = {
        "signals_total": signals_total,
        "source_diversity": source_diversity,
        "signals_last_30d": signals_last_30d,
    }
    uncertainty = []
    if signals_total <= 2:
        uncertainty.append("Evidence density is low; this wide band is uncertainty, not a negative judgment.")
    if signals_last_30d == 0:
        uncertainty.append("No Memory signal falls within the last 30 days of this snapshot.")
    return score, band, inputs, uncertainty


def endpoint_founder_memory_upsert(payload: dict[str, Any]) -> dict[str, Any]:
    founder_name = str(payload.get("founder_name") or "").strip()
    if not founder_name:
        raise ValueError("founder_name is required.")
    incoming_evidence = payload.get("evidence") or []
    if not isinstance(incoming_evidence, list):
        raise ValueError("evidence must be an array when provided.")
    key = _normalise_name(founder_name)
    aliases = payload.get("aliases") if isinstance(payload.get("aliases"), list) else []
    reference = founder_reference(founder_name, aliases)

    with _LOCK:
        store = _load()
        existing = store["founders"].get(key, {})
        profile_founder_id = str(payload.get("founder_id") or existing.get("founder_id") or reference["founder_id"])
        prior_evidence = existing.get("evidence", []) if isinstance(existing.get("evidence"), list) else []
        by_id = {
            str(item.get("evidence_id")): item
            for item in prior_evidence
            if isinstance(item, dict) and item.get("evidence_id")
        }
        for item in incoming_evidence:
            if not isinstance(item, dict):
                continue
            evidence_id = str(item.get("evidence_id") or stable_id("fev", founder_name, item.get("claim")))
            by_id[evidence_id] = {**item, "evidence_id": evidence_id}
        evidence = [normalise_memory_claim(item, profile_founder_id) for item in by_id.values()]
        timestamp = str(payload.get("snapshot_ts") or now_iso())
        snapshot_at = _parse_timestamp(payload.get("snapshot_ts"), _parse_timestamp(timestamp, datetime.now(timezone.utc)))
        score, band, score_inputs, uncertainty = _score(evidence, snapshot_at)
        previous_score = existing.get("founder_score") if isinstance(existing.get("founder_score"), dict) else None
        prior_value = int(previous_score.get("score", score)) if previous_score else score
        delta = score - prior_value
        trend = "up" if delta >= 3 else "down" if delta <= -3 else "flat"
        milestone = payload.get("milestone")
        milestones = existing.get("milestones", []) if isinstance(existing.get("milestones"), list) else []
        if isinstance(milestone, str) and milestone.strip():
            milestones.append({"description": milestone.strip(), "recorded_at": timestamp})

        combined_aliases = list(dict.fromkeys([*(existing.get("aliases", []) or []), *reference["aliases"]]))
        profile = {
            "founder_id": profile_founder_id,
            "founder_name": founder_name,
            "aliases": combined_aliases,
            "identity_resolution": founder_reference(founder_name, combined_aliases),
            "founder_score": {
                "score": score,
                "band": band,
                "trend": trend,
                "inputs": score_inputs,
                "uncertainty": uncertainty,
                "updated_at": timestamp,
            },
            "score_history": [
                *(existing.get("score_history", []) if isinstance(existing.get("score_history"), list) else []),
                {"ts": timestamp, "score": score, "band": band},
            ][-50:],
            "milestones": milestones[-100:],
            "evidence": evidence,
            "updated_at": timestamp,
        }
        store["founders"][key] = profile
        _save(store)
    return profile


def endpoint_founder_memory_get(payload: dict[str, Any]) -> dict[str, Any]:
    founder_name = str(payload.get("founder_name") or "").strip()
    if not founder_name:
        raise ValueError("founder_name is required.")
    with _LOCK:
        profile = _load()["founders"].get(_normalise_name(founder_name))
    if profile is None:
        reference = founder_reference(founder_name)
        return {
            "founder_id": reference["founder_id"],
            "founder_name": founder_name,
            "aliases": [],
            "identity_resolution": reference,
            "founder_score": {
                "score": 35,
                "band": 30,
                "trend": "flat",
                "inputs": {"signals_total": 0, "source_diversity": 0, "signals_last_30d": 0},
                "uncertainty": [
                    "No persistent founder evidence yet. This wide band is uncertainty, not a negative judgment."
                ],
                "updated_at": now_iso(),
            },
            "score_history": [],
            "milestones": [],
            "evidence": [],
            "updated_at": now_iso(),
        }
    return profile


def endpoint_founder_memory_resolve(payload: dict[str, Any]) -> dict[str, Any]:
    founder_name = str(payload.get("founder_name") or "").strip()
    aliases = payload.get("aliases") if isinstance(payload.get("aliases"), list) else []
    return founder_reference(founder_name, aliases)
