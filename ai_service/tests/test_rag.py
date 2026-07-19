"""Grounding tests for Founder Memory retrieval."""

from __future__ import annotations

import unittest

from ai_service.rag import answer_founder_memory


class FounderMemoryRagTests(unittest.TestCase):
    def test_deterministic_mode_returns_only_relevant_memory_citations(self) -> None:
        result = answer_founder_memory(
            {
                "message": "What technical evidence exists for Ada?",
                "history": [],
                "chunks": [
                    {
                        "chunk_id": "rag_ada",
                        "founder_id": "fndr_ada",
                        "founder_name": "Ada Example",
                        "source_type": "evidence",
                        "label": "Evidence · github",
                        "content": "Ada maintains a technical GPU inference repository.",
                    },
                    {
                        "chunk_id": "rag_bob",
                        "founder_id": "fndr_bob",
                        "founder_name": "Bob Example",
                        "source_type": "memo",
                        "label": "Investment memo",
                        "content": "Bob sells restaurant software.",
                    },
                ],
            }
        )

        self.assertFalse(result["insufficient_evidence"])
        self.assertEqual(result["cited_chunk_ids"], ["rag_ada"])
        self.assertIn("[1]", result["answer"])

    def test_deterministic_mode_refuses_when_memory_is_unrelated(self) -> None:
        result = answer_founder_memory(
            {
                "message": "What is the cap table?",
                "history": [],
                "chunks": [
                    {
                        "chunk_id": "rag_product",
                        "founder_id": "fndr_ada",
                        "founder_name": "Ada Example",
                        "source_type": "evidence",
                        "label": "Product evidence",
                        "content": "Ada shipped an observability tool.",
                    }
                ],
            }
        )

        self.assertTrue(result["insufficient_evidence"])
        self.assertEqual(result["cited_chunk_ids"], [])


if __name__ == "__main__":
    unittest.main()
