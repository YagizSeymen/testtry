from __future__ import annotations

from fastapi.testclient import TestClient

from tests.test_application_pipeline import NEURALKIT_DECK


def _run_to_memo(client: TestClient) -> str:
    created = client.post(
        "/api/applications",
        json={"company_name": "NeuralKit (Synthetic)", "deck_text": NEURALKIT_DECK},
    ).json()
    app_id = created["application_id"]
    assert client.post(f"/api/applications/{app_id}/screen").status_code == 200
    assert client.post(f"/api/applications/{app_id}/diligence").status_code == 200
    assert client.post(f"/api/applications/{app_id}/memo").status_code == 200
    return app_id


def test_human_gate_queue_decide_audit_metrics(client: TestClient) -> None:
    app_id = _run_to_memo(client)

    queue = client.get("/api/decisions/queue").json()
    assert any(item["application_id"] == app_id for item in queue)
    item = next(i for i in queue if i["application_id"] == app_id)
    assert item["company"] == "NeuralKit (Synthetic)"
    assert item["recommendation"]["amount"] == 100000
    assert item["memo_id"]

    # Cannot decide without memo — covered by another app; this one has memo.
    decided = client.post(
        f"/api/decisions/{app_id}/decide",
        json={"action": "approve", "approver": "Yuning"},
    )
    assert decided.status_code == 200, decided.text
    body = decided.json()
    assert body["status"] == "approved"
    assert body["audit_id"].startswith("audit_")

    # Removed from open queue
    queue_after = client.get("/api/decisions/queue").json()
    assert not any(item["application_id"] == app_id for item in queue_after)

    # Idempotent conflict
    again = client.post(
        f"/api/decisions/{app_id}/decide",
        json={"action": "reject", "approver": "Yuning"},
    )
    assert again.status_code == 409

    audit = client.get("/api/audit", params={"founder_id": "fndr_syn_001"}).json()
    assert any(row["stage"] == "decision" and row["action"] == "approved" for row in audit)
    assert any(row["actor"] == "Yuning" for row in audit)

    metrics = client.get("/api/metrics").json()
    assert metrics["funnel"]["sourced"] >= 1
    assert metrics["funnel"]["screened"] >= 1
    assert metrics["funnel"]["diligenced"] >= 1
    assert metrics["funnel"]["decided"] >= 1
    assert metrics["signal_to_decision_min"] is not None
    assert metrics["signal_to_decision_min"] >= 0


def test_decide_requires_memo(client: TestClient) -> None:
    created = client.post(
        "/api/applications",
        json={"company_name": "NeuralKit (Synthetic)", "deck_text": NEURALKIT_DECK},
    ).json()
    app_id = created["application_id"]
    resp = client.post(
        f"/api/decisions/{app_id}/decide",
        json={"action": "approve", "approver": "Yuning"},
    )
    assert resp.status_code == 409
