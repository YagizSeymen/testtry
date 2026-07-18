import os
import tempfile
import unittest

from ai_service import crawler, memory, sourcing
from ai_service.sourcing_orchestration import run_sourcing_workflow


SOURCE = {
    "source_id": "src_aster",
    "url": "https://example.com/aster",
    "title": "Aster Labs launch",
    "kind": "product_launch",
    "fetched_at": "2026-07-19T00:00:00Z",
}
PAGE_TEXT = """
Aster Labs is a Berlin company building model-serving infrastructure for enterprise AI teams.
Co-founder Ada Example is an engineer who maintains an open source GitHub repository for GPU inference.
The team shipped its production platform and won a European AI hackathon in 2025.
Aster has signed five enterprise design partners and is running paid customer pilots.
"""


class SourcingPipelineTest(unittest.TestCase):
    def test_thesis_to_source_backed_ranked_candidate(self):
        payload = {
            "thesis": "Find technical founders in Europe working on AI infrastructure with execution signals, no prior VC funding, and traction.",
            "candidate_documents": [
                {
                    "candidate": {
                        "company_name": "Aster Labs",
                        "company_url": "https://aster.example",
                        "founder_names": ["Ada Example"],
                    },
                    "source": SOURCE,
                    "page_text": PAGE_TEXT,
                }
            ],
        }
        plan = sourcing.endpoint_sourcing_plan(payload)
        self.assertEqual(len(plan["queries"]), 6)
        discovery = sourcing.endpoint_candidates_discover({**payload, "sourcing_plan": plan})
        self.assertEqual(len(discovery["candidates"]), 1)
        self.assertEqual(discovery["candidates"][0]["lifecycle_status"], "discovered")
        self.assertEqual(discovery["candidates"][0]["founder_refs"][0]["founder_id"], memory.founder_reference("Ada Example")["founder_id"])
        signals = {item["signal_type"] for item in discovery["evidence"]}
        self.assertTrue({"europe_location", "technical_founder", "ai_infrastructure", "execution", "product_traction"} <= signals)
        self.assertTrue(all("trust_score" in item and "trust_status" in item for item in discovery["evidence"]))

        ranking = sourcing.endpoint_candidates_rank({"discovery": discovery})
        candidate = ranking["ranked_candidates"][0]
        self.assertEqual(candidate["status"], "candidate")
        funding = next(item for item in candidate["eligibility"] if item["criterion"] == "no_previous_vc_funding")
        self.assertEqual(funding["status"], "no_public_evidence")
        self.assertTrue(candidate["manual_review_required"])

    def test_langgraph_sourcing_workflow(self):
        result = run_sourcing_workflow(
            {
                "thesis": "Technical founders in Europe building AI infrastructure.",
                "candidate_documents": [
                    {
                        "candidate": {"company_name": "Aster Labs", "founder_names": ["Ada Example"]},
                        "source": SOURCE,
                        "page_text": PAGE_TEXT,
                    }
                ],
            }
        )
        self.assertIn("ranking", result)
        self.assertEqual(result["trace"][-1], "candidate_rank:deterministic:evidence_gated")
        self.assertTrue(result["audit_events"])


class FounderMemoryTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_path = os.environ.get("VC_BRAIN_MEMORY_PATH")
        os.environ["VC_BRAIN_MEMORY_PATH"] = os.path.join(self.temp_dir.name, "memory.json")

    def tearDown(self):
        if self.previous_path is None:
            os.environ.pop("VC_BRAIN_MEMORY_PATH", None)
        else:
            os.environ["VC_BRAIN_MEMORY_PATH"] = self.previous_path
        self.temp_dir.cleanup()

    def test_cold_start_is_provisional_not_negative_and_score_persists(self):
        cold = memory.endpoint_founder_memory_get({"founder_name": "New Founder"})
        self.assertEqual(cold["founder_score"]["score"], 50)
        self.assertEqual(cold["founder_score"]["confidence"], "low")
        self.assertIn("not a negative judgment", cold["founder_score"]["uncertainty"][0])

        first = memory.endpoint_founder_memory_upsert(
            {
                "founder_name": "New Founder",
                "evidence": [
                    {"evidence_id": "ev_one", "claim": "Maintains an open source GitHub repository.", "quote": "GitHub repository"}
                ],
                "milestone": "Open-source project shipped",
            }
        )
        second = memory.endpoint_founder_memory_upsert(
            {
                "founder_name": "New Founder",
                "evidence": [
                    {"evidence_id": "ev_two", "claim": "Won a hackathon and launched a production product.", "quote": "Won a hackathon"}
                ],
            }
        )
        self.assertGreater(second["founder_score"]["score"], first["founder_score"]["score"])
        self.assertGreaterEqual(len(second["score_history"]), 2)
        self.assertEqual(len(second["milestones"]), 1)
        self.assertEqual(second["evidence"][0]["founder_id"], second["founder_id"])
        self.assertIn("source_url", second["evidence"][0])


class CrawlerGuardrailTest(unittest.TestCase):
    def test_html_extraction_and_private_host_block(self):
        text, title = crawler.html_to_text("<html><title>Aster</title><body>Visible <script>hidden</script> text</body></html>")
        self.assertEqual(title, "Aster")
        self.assertIn("Visible", text)
        self.assertNotIn("hidden", text)
        with self.assertRaises(crawler.CrawlError):
            crawler.validate_public_url("http://127.0.0.1/internal")


if __name__ == "__main__":
    unittest.main()
