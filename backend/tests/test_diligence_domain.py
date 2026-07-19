from __future__ import annotations

from app.domain.diligence import guard_memo_recommendation, map_trust, normalize_diligence_row


def test_map_trust_supported_levels() -> None:
    assert map_trust("supported", 2) == "high"
    assert map_trust("supported", 1) == "med"
    assert map_trust("supported", 0) == "low"
    assert map_trust("contradicted", 3) == "low"


def test_normalize_diligence_null_span_becomes_unverifiable() -> None:
    row = normalize_diligence_row(
        claim_id="c1",
        verdict="supported",
        evidence_ids=["s1", "s2"],
        valid_signal_ids={"s1", "s2"},
        source_span=None,
        note="x",
    )
    assert row["verdict"] == "unverifiable"
    assert row["evidence"] == []
    assert row["trust"] == "low"


def test_guard_memo_forces_invest_false_without_based_on() -> None:
    out = guard_memo_recommendation(
        based_on=["c1"],
        claims=[{"claim_id": "c1", "source_span": None}],
        diligence_claims=[{"claim_id": "c1", "verdict": "supported"}],
        invest=True,
        rationale="r",
    )
    assert out["invest"] is False
    assert out["based_on"] == []
