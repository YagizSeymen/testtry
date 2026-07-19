"""Regression tests for the backend-owned deterministic trust boundaries."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from backend.main import PostgresConnection, Store, decision_brief, founder_search_match, postgres_sql, validator_report


class StoreTests(unittest.TestCase):
    def test_application_research_is_idempotent_and_product_copy_does_not_inflate_founder_score(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "firstcheck.db")
            created = store.create_application(
                "Mailwarm",
                "Founder: Amine Benjelloun\nMailwarm is an email deliverability platform.",
                {
                    "founder_name": "Amine Benjelloun",
                    "claims": [
                        {
                            "claim_id": "clm_mailwarm_product",
                            "type": "product",
                            "text": "Mailwarm is an email deliverability platform.",
                            "source_span": "Mailwarm is an email deliverability platform.",
                        }
                    ],
                },
            )
            research = {
                "observations": [
                    {
                        "evidence_type": "product",
                        "source_relationship": "first_party",
                        "claim": "Mailwarm provides email deliverability tooling.",
                        "source_url": "https://example.com/mailwarm",
                        "crawl_verified": True,
                    },
                    {
                        "evidence_type": "technical_background",
                        "source_relationship": "independent",
                        "claim": "Amine Benjelloun built the Mailwarm product.",
                        "source_url": "https://example.com/amine",
                        "crawl_verified": True,
                    },
                ],
                "limitations": ["Revenue was not independently corroborated."],
            }
            self.assertEqual(store.ingest_application_research(created["application_id"], research), (2, 2))
            self.assertEqual(store.ingest_application_research(created["application_id"], research), (0, 2))
            profile = store.founder_profile(created["founder_id"])
            score = store.score(created["founder_id"])

        self.assertEqual(len(profile["signals"]), 2)
        self.assertEqual(score["score"], 49)

    def test_validator_report_separates_verified_unverified_and_speculation(self) -> None:
        report = validator_report(
            {
                "objections": [
                    {"verification": "verified", "targets": ["clm_one"], "evidence": ["sig_one"]},
                    {"verification": "unverified", "targets": ["clm_two"], "evidence": ["sig_two"]},
                    {"verification": "n/a", "targets": ["clm_three"], "evidence": None},
                ]
            }
        )

        self.assertEqual(report["stats"], {"verified": 1, "unverified": 1, "n/a": 1})
        self.assertEqual(len(report["findings"]), 3)
        self.assertIn("does not make an investment decision", report["summary"])

    def test_existing_application_founder_axis_is_recalibrated_from_memory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "firstcheck.db")
            created = store.create_application(
                "Dummy Co",
                "This is placeholder text with no founder evidence.",
                {
                    "founder_name": "Unknown founder",
                    "claims": [
                        {
                            "claim_id": "clm_dummy",
                            "type": "team",
                            "text": "This is placeholder text with no founder evidence.",
                            "source_span": "This is placeholder text with no founder evidence.",
                        }
                    ],
                },
            )
            store.update_stage(
                created["application_id"],
                "axes_json",
                {
                    "founder": {"score": 10, "trend": "up", "rationale": "Old inflated score"},
                    "market": {"rating": "neutral", "rationale": "Unknown"},
                    "idea_vs_market": {"verdict": "fails", "rationale": "Unknown"},
                },
                "screen",
                "Legacy screen",
            )
            application = store.application(created["application_id"])

        self.assertEqual(application["axes"]["founder"]["score"], 2)
        self.assertIn("0 independent Memory signals", application["axes"]["founder"]["rationale"])

    def test_memory_search_supports_partial_technical_ai_and_name_queries(self) -> None:
        profile = {
            "name": "Ada Example",
            "headline": "ML platform engineer",
            "location": "Austin",
            "origin": "github",
            "bio": "Builds language-model evaluation tools.",
        }
        signals = [
            {
                "signal_id": "sig_ada",
                "ts": "2026-07-19T00:00:00Z",
                "source": "github",
                "text": "Released an NLP model evaluation repository.",
                "url": "https://github.com/example/ada",
            }
        ]

        technical = founder_search_match(
            "technical",
            {"technical_founder": True, "sectors": [], "geos": [], "shipped_within_days": None, "prior_vc": None},
            profile,
            signals,
        )
        ai = founder_search_match(
            "AI",
            {"technical_founder": None, "sectors": ["AI"], "geos": [], "shipped_within_days": None, "prior_vc": None},
            profile,
            signals,
        )
        name = founder_search_match(
            "Ada",
            {"technical_founder": None, "sectors": [], "geos": [], "shipped_within_days": None, "prior_vc": None},
            profile,
            signals,
        )

        self.assertEqual(technical, ["Technical founder"])
        self.assertEqual(ai, ["AI"])
        self.assertEqual(name, ["Memory text match"])
        self.assertEqual(
            founder_search_match(
                "quantum",
                {"technical_founder": None, "sectors": [], "geos": [], "shipped_within_days": None, "prior_vc": None},
                profile,
                signals,
            ),
            [],
        )

    def test_postgres_adapter_translates_store_placeholders(self) -> None:
        class RecordingConnection:
            def __init__(self) -> None:
                self.calls: list[tuple[str, tuple[object, ...]]] = []

            def execute(self, statement: str, parameters: tuple[object, ...]) -> str:
                self.calls.append((statement, parameters))
                return "cursor"

        raw = RecordingConnection()
        connection = PostgresConnection(raw)

        self.assertEqual(postgres_sql("SELECT * FROM founders WHERE founder_id = ?"), "SELECT * FROM founders WHERE founder_id = %s")
        self.assertEqual(
            postgres_sql("SELECT * FROM signals WHERE text LIKE 'Live %' AND founder_id = ?"),
            "SELECT * FROM signals WHERE text LIKE 'Live %%' AND founder_id = %s",
        )
        self.assertEqual(connection.execute("UPDATE thesis SET payload = ?", ("{}",)), "cursor")
        self.assertEqual(raw.calls, [("UPDATE thesis SET payload = %s", ("{}",))])

    def test_live_discovery_promotes_review_leads_but_excludes_funded_candidates(self) -> None:
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
                    {
                        "candidate_id": "cand_unproven",
                        "evidence_id": "ev_unproven_launch",
                        "signal_type": "execution",
                        "claim": "Unproven Founder shipped a public NLP demo.",
                        "source_url": "https://example.com/unproven-launch",
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
            self.assertEqual(store.ingest_live_discovery(live_result), (2, 3))
            dashboard = store.dashboard()
            profile = store.founder_profile(next(item["founder_id"] for item in dashboard if item["name"] == "Ada Live"))

        self.assertEqual(profile["profile"]["origin"], "github")
        self.assertEqual({signal["source"] for signal in profile["signals"]}, {"github", "web"})
        self.assertNotIn("Funded Founder", [item["name"] for item in dashboard])
        self.assertIn("Unproven Founder", [item["name"] for item in dashboard])

    def test_live_discovery_deduplicates_one_source_claim_across_categories(self) -> None:
        live_result = {
            "discovery": {
                "evidence": [
                    {
                        "candidate_id": "cand_kirk",
                        "evidence_id": "ev_kirk_technical",
                        "signal_type": "technical_founder",
                        "claim": "Kirk Patrick is an ML platform engineer.",
                        "source_url": "https://example.com/kirk",
                        "captured_at": "2026-07-19T00:00:00Z",
                    },
                    {
                        "candidate_id": "cand_kirk",
                        "evidence_id": "ev_kirk_traction",
                        "signal_type": "product_traction",
                        "claim": "Kirk Patrick is an ML platform engineer.",
                        "source_url": "https://example.com/kirk",
                        "captured_at": "2026-07-19T00:00:00Z",
                    },
                    {
                        "candidate_id": "cand_kirk",
                        "evidence_id": "ev_kirk_execution",
                        "signal_type": "execution",
                        "claim": "Kirk Patrick shipped an ML platform for regulated teams.",
                        "source_url": "https://example.com/kirk",
                        "captured_at": "2026-07-19T00:00:00Z",
                    },
                ]
            },
            "ranking": {
                "ranked_candidates": [
                    {
                        "candidate_id": "cand_kirk",
                        "company_name": "Kirk Platform",
                        "founder_names": ["Kirk Patrick"],
                        "status": "candidate",
                    }
                ]
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "firstcheck.db")
            self.assertEqual(store.ingest_live_discovery(live_result), (1, 2))
            kirk_id = next(item["founder_id"] for item in store.dashboard() if item["name"] == "Kirk Patrick")
            profile = store.founder_profile(kirk_id)

        self.assertEqual(len(profile["signals"]), 2)
        self.assertEqual(sum("ML platform engineer" in signal["text"] for signal in profile["signals"]), 1)

    def test_live_signal_cleanup_removes_existing_duplicate_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "firstcheck.db")
            founder_id = store.resolve_or_create_founder("Kirk Patrick")
            with store.connection() as db:
                db.execute(
                    "INSERT INTO signals VALUES(?, ?, ?, ?, ?, ?)",
                    ("sig_kirk_technical", founder_id, "2026-07-19T00:00:00Z", "web", "Live technical founder: Kirk Patrick is an ML platform engineer.", "https://example.com/kirk"),
                )
                db.execute(
                    "INSERT INTO signals VALUES(?, ?, ?, ?, ?, ?)",
                    ("sig_kirk_traction", founder_id, "2026-07-19T00:00:00Z", "web", "Live product traction: Kirk Patrick is an ML platform engineer.", "https://example.com/kirk"),
                )
            self.assertEqual(store.deduplicate_live_signals(), 1)
            profile = store.founder_profile(founder_id)

        self.assertEqual(len(profile["signals"]), 1)
        self.assertIn("technical founder", profile["signals"][0]["text"])

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
