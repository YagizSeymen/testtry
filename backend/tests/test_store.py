"""Regression tests for the backend-owned deterministic trust boundaries."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from backend.main import Store, decision_brief


class StoreTests(unittest.TestCase):
    def test_live_discovery_promotes_only_qualified_candidates(self) -> None:
        live_result = {
            "discovery": {
                "evidence": [
                    {
                        "candidate_id": "cand_live",
                        "evidence_id": "ev_live_technical",
                        "signal_type": "technical_founder",
                        "claim": "Ada Live maintains a public GPU inference repository.",
                        "source_url": "https://github.com/example/ada-inference",
                        "captured_at": "2026-07-19T00:00:00Z",
                    },
                    {
                        "candidate_id": "cand_live",
                        "evidence_id": "ev_live_traction",
                        "signal_type": "product_traction",
                        "claim": "The company reports paid design partners for its platform.",
                        "source_url": "https://example.com/ada-live-launch",
                        "captured_at": "2026-07-19T00:00:00Z",
                    },
                    {
                        "candidate_id": "cand_live",
                        "evidence_id": "ev_live_technical_repeat",
                        "signal_type": "technical_founder",
                        "claim": "Ada Live maintains a second public GPU inference repository.",
                        "source_url": "https://github.com/example/ada-inference",
                        "captured_at": "2026-07-19T00:00:00Z",
                    },
                    {
                        "candidate_id": "cand_funded",
                        "evidence_id": "ev_funded",
                        "signal_type": "public_vc_funding",
                        "claim": "Funded Co announced a seed round.",
                        "source_url": "https://example.com/funded-announcement",
                        "captured_at": "2026-07-19T00:00:00Z",
                    },
                ]
            },
            "ranking": {
                "ranked_candidates": [
                    {
                        "candidate_id": "cand_live",
                        "company_name": "Ada Systems",
                        "founder_names": ["Ada Live"],
                        "status": "candidate",
                    },
                    {
                        "candidate_id": "cand_funded",
                        "company_name": "Funded Co",
                        "founder_names": ["Funded Founder"],
                        "status": "excluded",
                    },
                    {
                        "candidate_id": "cand_unproven",
                        "company_name": "Unproven Co",
                        "founder_names": ["Unproven Founder"],
                        "status": "needs_review",
                    },
                ]
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "firstcheck.db")
            self.assertEqual(store.ingest_live_discovery(live_result), (1, 2))
            dashboard = store.dashboard()
            profile = store.founder_profile(next(item["founder_id"] for item in dashboard if item["name"] == "Ada Live"))

        self.assertEqual(profile["profile"]["origin"], "github")
        self.assertEqual({signal["source"] for signal in profile["signals"]}, {"github", "web"})
        self.assertNotIn("Funded Founder", [item["name"] for item in dashboard])
        self.assertNotIn("Unproven Founder", [item["name"] for item in dashboard])

    def test_inbound_application_converges_on_cached_founder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "firstcheck.db")
            maya_id = store.resolve_or_create_founder("Maya Chen")
            deck_text = "Founder: Maya Chen\nNeuralKit shipped a GPU scheduling platform for AI infrastructure teams."
            application = store.create_application(
                "NeuralKit",
                deck_text,
                {
                    "founder_name": "Maya Chen",
                    "claims": [
                        {
                            "claim_id": "clm_test_product",
                            "type": "product",
                            "text": "NeuralKit shipped a GPU scheduling platform.",
                            "source_span": "NeuralKit shipped a GPU scheduling platform for AI infrastructure teams.",
                        }
                    ],
                },
            )

        self.assertEqual(application["founder_id"], maya_id)
        self.assertEqual(application["claims"][0]["source_span"], deck_text.split("\n", 1)[1])

    def test_cache_seed_is_repeatable_and_rejects_invalid_spans(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "firstcheck.db")
            self.assertEqual(store.seed_cache(), (0, 0))
            with self.assertRaises(HTTPException):
                store.create_application(
                    "Unsafe span",
                    "Founder: Maya Chen",
                    {
                        "founder_name": "Maya Chen",
                        "claims": [
                            {
                                "claim_id": "clm_invalid_span",
                                "type": "team",
                                "text": "Maya Chen has a strong team.",
                                "source_span": "This sentence does not appear in the deck.",
                            }
                        ],
                    },
                )

    def test_decision_brief_marks_verified_memo_claim_as_red(self) -> None:
        brief = decision_brief(
            {"claims": [{"claim_id": "clm_traction"}]},
            {"recommendation": {"based_on": ["clm_traction"]}},
            {
                "objections": [
                    {"targets": ["clm_traction"], "verification": "verified"},
                    {"targets": ["clm_traction"], "verification": "speculation"},
                ]
            },
        )

        self.assertEqual(brief["stats"]["verified_attacks"], 1)
        self.assertEqual([item["severity"] for item in brief["contested"]], ["red", "dim"])


if __name__ == "__main__":
    unittest.main()
