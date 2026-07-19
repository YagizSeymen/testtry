from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def _ensure_repo_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    root_str = str(repo_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


class IntelligenceService:
    """Narrow adapter over the AI lane. Routes never import LangGraph nodes."""

    def extract(self, *, company_name: str, deck_text: str) -> dict[str, Any]:
        _ensure_repo_on_path()
        from ai_service.pipeline import extract_application

        return extract_application({"company_name": company_name, "deck_text": deck_text})

    def screen(self, payload: dict[str, Any]) -> dict[str, Any]:
        _ensure_repo_on_path()
        from ai_service.pipeline import screen_application

        return screen_application(payload)

    def diligence(self, payload: dict[str, Any]) -> dict[str, Any]:
        _ensure_repo_on_path()
        from ai_service.pipeline import diligence_claims

        return diligence_claims(payload)

    def memo(self, payload: dict[str, Any]) -> dict[str, Any]:
        _ensure_repo_on_path()
        from ai_service.pipeline import write_memo

        return write_memo(payload)

    def parse_query(self, *, q: str, thesis: dict[str, Any]) -> dict[str, Any]:
        _ensure_repo_on_path()
        from ai_service.pipeline import parse_query

        return parse_query({"q": q, "thesis": thesis})
