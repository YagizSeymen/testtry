from __future__ import annotations

from fastapi.testclient import TestClient


def test_query_matches_seeded_founder(client: TestClient) -> None:
    resp = client.post(
        "/api/query",
        json={"q": "technical founder, AI infra, shipped last 30 days, no prior VC"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["filter"]["technical_founder"] is True
    assert data["filter"]["prior_vc"] is False
    assert any(r["founder_id"] == "fndr_syn_001" for r in data["results"])
    match = next(r for r in data["results"] if r["founder_id"] == "fndr_syn_001")
    assert match["why_matched"]


def test_activate_returns_draft_not_sent(client: TestClient) -> None:
    resp = client.post("/api/founders/fndr_syn_001/activate")
    assert resp.status_code == 200, resp.text
    draft = resp.json()["outreach_draft"]
    assert "will not be sent" in draft.lower() or "not be sent" in draft.lower()
    assert "Maya" in draft


def test_scan_run_is_cached(client: TestClient) -> None:
    first = client.post("/api/scan/run").json()
    assert first["cached"] is True
    second = client.post("/api/scan/run").json()
    assert second["cached"] is True
    # Already seeded by lifespan → subsequent scan adds nothing.
    assert second["new_founders"] == 0
    assert second["new_signals"] == 0
