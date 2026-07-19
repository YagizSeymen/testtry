"""Grounding tests for Founder Memory retrieval."""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from ai_service.rag import answer_founder_memory


class FounderMemoryRagTests(unittest.TestCase):
    @patch("openai.OpenAI")
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "VC_BRAIN_LLM_MODE": "openai"}, clear=False)
    def test_openai_chat_bounds_output_and_uses_conversation_cache_key(self, openai_class) -> None:
        client = openai_class.return_value
        client.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(embedding=[1.0, 0.0]), SimpleNamespace(embedding=[1.0, 0.0])]
        )
        client.responses.create.return_value = SimpleNamespace(
            output_text='{"answer":"Ada shipped a GPU tool [1].","cited_chunk_ids":["rag_ada"],"insufficient_evidence":false}'
        )

        result = answer_founder_memory(
            {
                "message": "What did Ada ship?",
                "chat_id": "chat_ada_1234",
                "history": [],
                "chunks": [
                    {
                        "chunk_id": "rag_ada",
                        "founder_id": "fndr_ada",
                        "founder_name": "Ada Example",
                        "source_type": "evidence",
                        "label": "Evidence · github",
                        "content": "Ada shipped a GPU tool.",
                        "embedding_json": None,
                    }
                ],
            }
        )

        request = client.responses.create.call_args.kwargs
        self.assertEqual(request["reasoning"], {"effort": "none"})
        self.assertEqual(request["max_output_tokens"], 700)
        self.assertFalse(request["store"])
        self.assertTrue(request["prompt_cache_key"].startswith("founder-memory-"))
        self.assertEqual(result["cited_chunk_ids"], ["rag_ada"])
        self.assertIn("rag_ada", result["embedding_updates"])

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
