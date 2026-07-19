from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("FIRSTCHECK_DATABASE_URL", f"sqlite:///{db_path}")

    from app.db import reset_db_runtime

    reset_db_runtime()

    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client

    reset_db_runtime()
