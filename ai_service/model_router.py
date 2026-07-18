"""Model routing for the VC Brain's bounded AI workflow.

The default mode is deterministic so frontend and backend work without API
credentials. Set `VC_BRAIN_LLM_MODE=openai` and `OPENAI_API_KEY` to route
stages through the OpenAI Responses API.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable


LUNA_MODEL = "gpt-5.6-luna"
TERRA_MODEL = "gpt-5.6-terra"

MODEL_BY_STAGE = {
    "research_plan": LUNA_MODEL,
    "evidence_extract": LUNA_MODEL,
    "screen_score": TERRA_MODEL,
    "memo_write": TERRA_MODEL,
    "adversary_write": TERRA_MODEL,
    "truth_gap_verify": TERRA_MODEL,
    "verdict_brief": LUNA_MODEL,
}

STAGE_INSTRUCTIONS = {
    "research_plan": "Generate focused research queries and public target URLs. Do not make an investment recommendation.",
    "evidence_extract": "Extract only source-backed claims. Preserve exact supporting quotes and mark uncertainty rather than guessing.",
    "screen_score": "Assess the supplied evidence. Be explicit about uncertainty and missing evidence. Do not invent facts.",
    "memo_write": "Write an evidence-backed investment memo. Every factual claim must reference supplied evidence IDs. Flag data gaps explicitly.",
    "adversary_write": "Write one bounded counter-case against the memo. Do not debate or add facts. Every objection needs evidence IDs or an explicit speculation label.",
    "truth_gap_verify": "Treat each objection as a claim and verify it only against supplied Memory evidence. Badge it verified, unverified, or speculation.",
    "verdict_brief": "Summarize verified objections for a human reviewer. This is non-authoritative and must not make the final decision.",
}


class ModelProviderError(RuntimeError):
    """Raised when a configured model provider cannot produce valid JSON."""


@dataclass(frozen=True)
class ModelInvocation:
    stage: str
    model: str
    mode: str


class ModelRouter:
    """Routes fixed workflow stages to Luna or Terra.

    It intentionally does not expose an autonomous agent loop. Every stage is
    selected by the application, has a fixed prompt purpose, and must return
    one JSON result to the next bounded stage.
    """

    def __init__(self, mode: str | None = None) -> None:
        self.mode = (mode or os.getenv("VC_BRAIN_LLM_MODE", "deterministic")).lower()

    def invocation(self, stage: str) -> ModelInvocation:
        if stage not in MODEL_BY_STAGE:
            raise ValueError(f"Unknown AI stage: {stage}")
        return ModelInvocation(stage=stage, model=MODEL_BY_STAGE[stage], mode=self.mode)

    def run(
        self,
        stage: str,
        payload: dict[str, Any],
        fallback: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        invocation = self.invocation(stage)
        if invocation.mode == "deterministic":
            return fallback(payload)
        if invocation.mode != "openai":
            raise ModelProviderError(
                "VC_BRAIN_LLM_MODE must be 'deterministic' or 'openai'."
            )
        return self._run_openai(invocation, payload)

    def _run_openai(self, invocation: ModelInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ModelProviderError(
                "OPENAI_API_KEY is required when VC_BRAIN_LLM_MODE=openai."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ModelProviderError(
                "Install ai_service/requirements.txt to enable OpenAI model routing."
            ) from exc

        client = OpenAI(api_key=api_key)
        developer_prompt = (
            "You are one fixed stage in The VC Brain's bounded workflow. "
            f"Stage: {invocation.stage}. {STAGE_INSTRUCTIONS[invocation.stage]} "
            "Return only a JSON object matching the requested API-contract response shape."
        )
        response = client.responses.create(
            model=invocation.model,
            input=[
                {"role": "developer", "content": developer_prompt},
                {"role": "user", "content": json.dumps(payload)},
            ],
        )
        try:
            result = json.loads(response.output_text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ModelProviderError(
                f"{invocation.model} returned non-JSON output for {invocation.stage}."
            ) from exc
        if not isinstance(result, dict):
            raise ModelProviderError(
                f"{invocation.model} returned a non-object JSON value for {invocation.stage}."
            )
        return result


def model_manifest() -> dict[str, str]:
    """Return the judge-facing mapping of workflow stages to model IDs."""

    return dict(MODEL_BY_STAGE)
