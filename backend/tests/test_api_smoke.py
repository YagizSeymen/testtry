from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_thesis_get_seeded(client: TestClient) -> None:
    data = client.get("/api/thesis").json()
    assert data["thesis"]["check_size"] == 100000
    assert data["thesis"]["risk_appetite"] == "medium"
    assert "AI infrastructure" in data["thesis"]["sectors"]


def test_thesis_replace(client: TestClient) -> None:
    body = {
        "thesis": {
            "sectors": ["devtools"],
            "stage": "seed",
            "geo": ["Europe"],
            "check_size": 100000,
            "risk_appetite": "low",
        }
    }
    assert client.post("/api/thesis", json=body).json() == {"ok": True}
    assert client.get("/api/thesis").json()["thesis"]["sectors"] == ["devtools"]


def test_dashboard_seeded_founder(client: TestClient) -> None:
    rows = client.get("/api/dashboard").json()
    assert len(rows) == 1
    row = rows[0]
    assert row["founder_id"] == "fndr_syn_001"
    assert row["origin"] == "synthetic"
    assert row["founder_score"] == 59
    assert row["band"] == 22
    assert row["trend"] == "up"
    assert row["has_open_app"] is True


def test_founder_detail(client: TestClient) -> None:
    data = client.get("/api/founders/fndr_syn_001").json()
    assert data["profile"]["name"] == "Maya Chen (Synthetic)"
    assert len(data["signals"]) == 6
    assert data["signals"][0]["source"] == "synthetic"
    assert "app_syn_001" in data["applications"]
    assert len(data["score_history"]) == 2
