from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field


def _repo_root() -> Path:
    # backend/app/config.py → backend/ → repo root
    return Path(__file__).resolve().parents[2]


def _default_database_url() -> str:
    return os.getenv(
        "FIRSTCHECK_DATABASE_URL",
        f"sqlite:///{_repo_root() / 'backend' / 'firstcheck.db'}",
    )


class Settings(BaseModel):
    """Runtime settings. Keep env surface minimal (AGENTS.md)."""

    app_name: str = "FirstCheck API"
    database_url: str = Field(default_factory=_default_database_url)
    fixtures_dir: Path = Field(default_factory=lambda: _repo_root() / "data" / "fixtures")
    seed_on_startup: bool = True


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
