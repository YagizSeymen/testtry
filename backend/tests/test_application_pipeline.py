from __future__ import annotations

from fastapi.testclient import TestClient

NEURALKIT_DECK = """
Founder: Maya Chen (Synthetic)

We have reached $50K in monthly recurring revenue.
Our initial customers are AI infrastructure teams.
The product is a model observability workflow for infrastructure buyers.
""".strip()


def test_application_pipeline_golden_path(client: TestClient) -> None:
    created = client.post(
        "/api/applications",
        json={"company_name": "NeuralKit (Synthetic)", "deck_text": NEURALKIT_DECK},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["founder_id"] == "fndr_syn_001"  # resolved to seeded Maya Chen
    assert len(body["claims"]) >= 2
    app_id = body["application_id"]

    # Version A: stages null after extract
    aggregate = client.get(f"/api/applications/{app_id}").json()
    assert aggregate["axes"] is None
    assert aggregate["diligence"] is None
    assert aggregate["memo"] is None
    assert aggregate["adversarial"] is None
    assert aggregate["decision_brief"] is None
    assert aggregate["evidence"] == []

    # Prerequisites
    assert client.post(f"/api/applications/{app_id}/diligence").status_code == 409
    assert client.post(f"/api/applications/{app_id}/memo").status_code == 409

    axes = client.post(f"/api/applications/{app_id}/screen").json()
    assert "founder" in axes and "market" in axes and "idea_vs_market" in axes
    assert axes["founder"]["trend"] in {"up", "flat", "down"}

    diligence = client.post(f"/api/applications/{app_id}/diligence").json()
    by_id = {row["claim_id"]: row for row in diligence["claims"]}
    # Traction MRR should be contradicted by seeded pre-revenue HN-style signal.
    traction = next(c for c in body["claims"] if c["type"] == "traction")
    assert by_id[traction["claim_id"]]["verdict"] == "contradicted"
    assert by_id[traction["claim_id"]]["trust"] == "low"
    assert "Cap table: not disclosed" in diligence["gaps"]

    memo = client.post(f"/api/applications/{app_id}/memo").json()
    assert set(memo["sections"]) == {
        "snapshot",
        "hypotheses",
        "swot",
        "problem_product",
        "traction_kpis",
    }
    assert memo["recommendation"]["amount"] == 100000
    # Contradicted traction must not appear in based_on.
    assert traction["claim_id"] not in memo["recommendation"]["based_on"]

    final = client.get(f"/api/applications/{app_id}").json()
    assert final["axes"] is not None
    assert final["diligence"] is not None
    assert final["memo"] is not None
    assert len(final["evidence"]) >= 1
