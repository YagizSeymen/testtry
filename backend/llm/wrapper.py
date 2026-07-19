"""Single backend boundary for the fixed AI stages.

No prompts or model calls live in route handlers. The imported AI service uses
temperature-zero JSON mode when model mode is enabled and deterministic output
otherwise, which keeps the cache-first demo operational without credentials.
"""

from __future__ import annotations

from typing import Any

from ai_service import pipeline


class LLMWrapper:
    def extract(self, company_name: str, deck_text: str) -> dict[str, Any]:
        return pipeline.extract_application({"company_name": company_name, "deck_text": deck_text})

    def query(self, query: str, thesis: dict[str, Any]) -> dict[str, Any]:
        return pipeline.parse_query({"q": query, "thesis": thesis})

    def screen(self, payload: dict[str, Any]) -> dict[str, Any]:
        return pipeline.screen_application(payload)

    def diligence(self, claims: list[dict[str, Any]], signals: list[dict[str, Any]]) -> dict[str, Any]:
        return pipeline.diligence_claims({"claims": claims, "signals": signals})

    def memo(
        self,
        company_name: str,
        claims: list[dict[str, Any]],
        diligence: dict[str, Any],
        axes: dict[str, Any],
    ) -> dict[str, Any]:
        return pipeline.write_memo(
            {
                "company_name": company_name,
                "claims": claims,
                "diligence": diligence,
                "axes": axes,
            }
        )

    def adversary(
        self,
        memo: dict[str, Any],
        axes: dict[str, Any],
        claims: list[dict[str, Any]],
        signals: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return pipeline.write_adversary(
            {"memo": memo, "axes": axes, "claims": claims, "signals": signals}
        )

    def verify_adversary(
        self,
        adversarial: dict[str, Any],
        claims: list[dict[str, Any]],
        signals: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return pipeline.verify_adversary(
            {"adversarial": adversarial, "claims": claims, "signals": signals}
        )
