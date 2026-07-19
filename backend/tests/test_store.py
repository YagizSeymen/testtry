"""Regression tests for the backend-owned deterministic trust boundaries."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend.main import PostgresConnection, Store, decision_brief, founder_memory_chat, founder_search_match, postgres_sql, validator_report


class StoreTests(unittest.TestCase):
    def test_signal_diversity_metrics_use_normalized_stored_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "firstcheck.db")
            with store.connection() as db:
                founder_id = db.execute("SELECT founder_id FROM founders ORDER BY founder_id LIMIT 1").fetchone()["founder_id"]
                db.execute(
                    "INSERT INTO signals VALUES(?, ?, ?, ?, ?, ?)",
                    ("sig_diversity_upper", founder_id, "2026-07-19T00:00:00Z", " GitHub ", "Upper source", None),
                )
                db.execute(
                    "INSERT INTO signals VALUES(?, ?, ?, ?, ?, ?)",
                    ("sig_diversity_lower", founder_id, "2026-07-19T00:00:01Z", "github", "Lower source", None),
                )
                expected_rows = db.execute(
                    """
                    SELECT LOWER(TRIM(source)) AS source, COUNT(*) AS count
                    FROM signals
                    WHERE TRIM(source) != ''
                    GROUP BY LOWER(TRIM(source))
                    ORDER BY count DESC, source ASC
                    """
                ).fetchall()
            metrics = store.metrics()

        expected = [{"source": row["source"], "count": row["count"]} for row in expected_rows]
        self.assertEqual(metrics["signal_diversity"]["sources"], expected)
        self.assertEqual(metrics["signal_diversity"]["distinct_sources"], len(expected))
        self.assertEqual(metrics["signal_diversity"]["total_signals"], sum(item["count"] for item in expected))
        github = next(item for item in expected if item["source"] == "github")
        self.assertGreaterEqual(github["count"], 2)

    def test_chat_id_remains_optional_for_existing_api_clients(self) -> None:
        with patch("backend.main.store.sync_rag_chunks", return_value=[]):
            response = founder_memory_chat({"message": "What evidence exists?", "history": []})

        self.assertTrue(response["insufficient_evidence"])
        self.assertEqual(response["citations"], [])

    def test_rag_chunks_cover_memory_and_reuse_only_current_embeddings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "firstcheck.db")
            created = store.create_application(
                "VectorWorks",
                "Founder: Ada Vector\nVectorWorks built an inference observability tool.",
                {
                    "founder_name": "Ada Vector",
                    "claims": [
                        {
                            "claim_id": "clm_vector_product",
                            "type": "product",
                            "text": "VectorWorks built an inference observability tool.",
                            "source_span": "VectorWorks built an inference observability tool.",
                        }
                    ],
                },
            )
            chunks = store.sync_rag_chunks(created["founder_id"])
            source_types = {chunk["source_type"] for chunk in chunks}
            claim_chunk = next(chunk for chunk in chunks if chunk["source_type"] == "claim")
            store.save_rag_embeddings({claim_chunk["chunk_id"]: [0.1, 0.2, 0.3]})
            with store.connection() as db:
                db.execute(
                    "UPDATE rag_chunks SET updated_at = ? WHERE chunk_id = ?",
                    ("2025-01-01T00:00:00Z", claim_chunk["chunk_id"]),
                )
            unchanged = store.sync_rag_chunks(created["founder_id"])
            unchanged_claim = next(chunk for chunk in unchanged if chunk["chunk_id"] == claim_chunk["chunk_id"])
            with store.connection() as db:
                db.execute(
                    "UPDATE claims SET text = ? WHERE claim_id = ?",
                    ("VectorWorks changed its product claim.", "clm_vector_product"),
                )
            changed = store.sync_rag_chunks(created["founder_id"])
            changed_claim = next(chunk for chunk in changed if chunk["chunk_id"] == claim_chunk["chunk_id"])

        self.assertTrue({"profile", "application", "claim"}.issubset(source_types))
        self.assertIsNotNone(unchanged_claim["embedding_json"])
        self.assertEqual(unchanged_claim["updated_at"], "2025-01-01T00:00:00Z")
        self.assertIsNone(changed_claim["embedding_json"])

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
        self.assertIn("0 score-eligible public Memory signals", application["axes"]["founder"]["rationale"])

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

    def test_memory_search_matches_fuzzy_company_and_application_context(self) -> None:
        profile = {
            "name": "Maya Chen",
            "headline": "Technical founder",
            "location": None,
            "origin": "inbound",
            "bio": "Founder introduced through an application.",
        }
        signals = [
            {
                "signal_id": "sig_maya",
                "ts": "2026-07-19T00:00:00Z",
                "source": "web",
                "text": "Built a GPU scheduling platform for ML teams.",
                "url": "https://neuralkit.example/product",
            }
        ]
        empty_filter = {
            "technical_founder": None,
            "sectors": [],
            "geos": [],
            "shipped_within_days": None,
            "prior_vc": None,
        }

        company = founder_search_match("NeuralKitt", empty_filter, profile, signals, ["NeuralKit"])
        related_copy = founder_search_match("GPU scheduler", empty_filter, profile, signals, ["NeuralKit"])

        self.assertIn("Company or application match", company)
        self.assertTrue(related_copy)

    def test_postgres_adapter_translates_store_placeholders(self) -> None:
        class RecordingConnection:
            def __init__(self) -> None:
                self.calls: list[tuple[str, tuple[object, ...]]] = []

            def execute(self, statement: str, parameters: tuple[object, ...]) -> str:
                self.calls.append((statement, parameters))
                return "cursor"

            def cursor(self):
                connection = self

                class RecordingCursor:
                    def __enter__(self):
                        return self

                    def __exit__(self, *_args: object) -> None:
                        return None

                    def executemany(self, statement: str, parameters: list[tuple[object, ...]]) -> None:
                        connection.calls.extend((statement, item) for item in parameters)

                return RecordingCursor()

        raw = RecordingConnection()
        connection = PostgresConnection(raw)

        self.assertEqual(postgres_sql("SELECT * FROM founders WHERE founder_id = ?"), "SELECT * FROM founders WHERE founder_id = %s")
        self.assertEqual(
            postgres_sql("SELECT * FROM signals WHERE text LIKE 'Live %' AND founder_id = ?"),
            "SELECT * FROM signals WHERE text LIKE 'Live %%' AND founder_id = %s",
        )
        self.assertEqual(connection.execute("UPDATE thesis SET payload = ?", ("{}",)), "cursor")
        connection.executemany("UPDATE rag_chunks SET embedding_json = ? WHERE chunk_id = ?", [("[]", "rag_1")])
        self.assertEqual(
            raw.calls,
            [
                ("UPDATE thesis SET payload = %s", ("{}",)),
                ("UPDATE rag_chunks SET embedding_json = %s WHERE chunk_id = %s", ("[]", "rag_1")),
            ],
        )

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

    def test_cofounder_evidence_is_attributed_and_latest_batch_replaces_new_badge(self) -> None:
        weave_result = {
            "discovery": {
                "evidence": [
                    {
                        "candidate_id": "cand_weave",
                        "evidence_id": "ev_kaan",
                        "signal_type": "technical_founder",
                        "claim": "Kaan led ML robotics research.",
                        "source_url": "https://www.ycombinator.com/companies/weave-robotics",
                        "captured_at": "2026-07-19T00:00:00Z",
                    },
                    {
                        "candidate_id": "cand_weave",
                        "evidence_id": "ev_evan_profile",
                        "signal_type": "technical_founder",
                        "claim": "Evan Wineland is a founder of Weave Robotics.",
                        "source_url": "https://www.linkedin.com/in/ecwineland?trk=public",
                        "captured_at": "2026-07-19T00:00:00Z",
                    },
                    {
                        "candidate_id": "cand_weave",
                        "evidence_id": "ev_product",
                        "signal_type": "product_traction",
                        "claim": "Weave Robotics deploys robots in customer homes.",
                        "source_url": "https://weaverobotics.com/customers",
                        "captured_at": "2026-07-19T00:00:00Z",
                    },
                    {
                        "candidate_id": "cand_weave",
                        "evidence_id": "ev_kaan_post",
                        "signal_type": "execution",
                        "claim": "Weave Robotics tested an early prototype in a real home.",
                        "source_url": "https://www.linkedin.com/posts/kaan-dogrusoz-073b748a_prototype-activity-1",
                        "captured_at": "2026-07-19T00:00:00Z",
                    },
                ]
            },
            "ranking": {
                "ranked_candidates": [
                    {
                        "candidate_id": "cand_weave",
                        "company_name": "Weave Robotics",
                        "founder_names": ["Evan Wineland", "Kaan Dogrusoz"],
                        "status": "candidate",
                    }
                ]
            },
        }
        later_result = {
            "discovery": {
                "evidence": [
                    {
                        "candidate_id": "cand_later",
                        "evidence_id": "ev_later",
                        "signal_type": "execution",
                        "claim": "Grace Hopper shipped Compiler Cloud.",
                        "source_url": "https://example.com/compiler-cloud",
                        "captured_at": "2026-07-19T01:00:00Z",
                    }
                ]
            },
            "ranking": {
                "ranked_candidates": [
                    {
                        "candidate_id": "cand_later",
                        "company_name": "Compiler Cloud",
                        "founder_names": ["Grace Hopper"],
                        "status": "candidate",
                    }
                ]
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "firstcheck.db")
            store.ingest_live_discovery(weave_result, "scan_weave")
            first_dashboard = store.dashboard()
            evan_id = next(item["founder_id"] for item in first_dashboard if item["name"] == "Evan Wineland")
            kaan_id = next(item["founder_id"] for item in first_dashboard if item["name"] == "Kaan Dogrusoz")
            evan_text = " ".join(signal["text"] for signal in store.founder_profile(evan_id)["signals"])
            kaan_text = " ".join(signal["text"] for signal in store.founder_profile(kaan_id)["signals"])

            self.assertNotIn("Kaan led", evan_text)
            self.assertNotIn("early prototype", evan_text)
            self.assertNotIn("Evan Wineland is", kaan_text)
            self.assertIn("early prototype", kaan_text)
            self.assertIn("customer homes", evan_text)
            self.assertIn("customer homes", kaan_text)
            self.assertTrue(next(item for item in first_dashboard if item["name"] == "Evan Wineland")["is_new"])
            self.assertTrue(next(item for item in first_dashboard if item["name"] == "Kaan Dogrusoz")["is_new"])

            store.ingest_live_discovery(later_result, "scan_later")
            second_dashboard = store.dashboard()

        self.assertFalse(next(item for item in second_dashboard if item["name"] == "Evan Wineland")["is_new"])
        self.assertFalse(next(item for item in second_dashboard if item["name"] == "Kaan Dogrusoz")["is_new"])
        self.assertTrue(next(item for item in second_dashboard if item["name"] == "Grace Hopper")["is_new"])

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

    def test_live_signal_cleanup_repairs_legacy_cofounder_cloning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "firstcheck.db")
            kaan_id = store.resolve_or_create_founder("Kaan Dogrusoz")
            evan_id = store.resolve_or_create_founder("Evan Wineland")
            with store.connection() as db:
                for founder_id in (kaan_id, evan_id):
                    db.execute(
                        "INSERT INTO signals VALUES(?, ?, ?, ?, ?, ?)",
                        (
                            f"sig_{founder_id}_kaan",
                            founder_id,
                            "2026-07-19T00:00:00Z",
                            "hn",
                            "Live technical founder: Kaan led ML robotics research.",
                            "https://www.ycombinator.com/companies/weave-robotics",
                        ),
                    )
                    db.execute(
                        "INSERT INTO signals VALUES(?, ?, ?, ?, ?, ?)",
                        (
                            f"sig_{founder_id}_product",
                            founder_id,
                            "2026-07-19T00:00:00Z",
                            "hn",
                            "Live product traction: Weave Robotics tested robots in customer homes.",
                            "https://www.ycombinator.com/companies/weave-robotics",
                        ),
                    )
            store.deduplicate_live_signals()
            evan_text = " ".join(signal["text"] for signal in store.founder_profile(evan_id)["signals"])
            kaan_text = " ".join(signal["text"] for signal in store.founder_profile(kaan_id)["signals"])

        self.assertNotIn("Kaan led", evan_text)
        self.assertIn("customer homes", evan_text)
        self.assertIn("Kaan led", kaan_text)

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
