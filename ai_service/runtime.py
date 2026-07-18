"""Public stage wrappers with deterministic and OpenAI-backed runtime modes."""

from __future__ import annotations

from typing import Any, Callable

from . import core
from .model_router import ModelRouter


StageFn = Callable[[dict[str, Any]], dict[str, Any]]

_FALLBACKS: dict[str, StageFn] = {
    "research_plan": core.endpoint_research_plan,
    "evidence_extract": core.endpoint_evidence_extract,
    "screen_score": core.endpoint_screen_score,
    "memo_write": core.endpoint_memo_write,
    "adversary_write": core.endpoint_adversary_write,
    "truth_gap_verify": core.endpoint_truth_gap_verify,
    "verdict_brief": core.endpoint_verdict_brief,
}


def execute(stage: str, payload: dict[str, Any]) -> dict[str, Any]:
    fallback = _FALLBACKS.get(stage)
    if fallback is None:
        raise ValueError(f"Unknown AI stage: {stage}")
    return ModelRouter().run(stage, payload, fallback)


def endpoint_research_plan(payload: dict[str, Any]) -> dict[str, Any]:
    return execute("research_plan", payload)


def endpoint_evidence_extract(payload: dict[str, Any]) -> dict[str, Any]:
    return execute("evidence_extract", payload)


def endpoint_screen_score(payload: dict[str, Any]) -> dict[str, Any]:
    return execute("screen_score", payload)


def endpoint_memo_write(payload: dict[str, Any]) -> dict[str, Any]:
    return execute("memo_write", payload)


def endpoint_adversary_write(payload: dict[str, Any]) -> dict[str, Any]:
    return execute("adversary_write", payload)


def endpoint_truth_gap_verify(payload: dict[str, Any]) -> dict[str, Any]:
    return execute("truth_gap_verify", payload)


def endpoint_verdict_brief(payload: dict[str, Any]) -> dict[str, Any]:
    return execute("verdict_brief", payload)
