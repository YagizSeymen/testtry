import unittest

from ai_service.examples.sample_payload import DEAL, PAGE_TEXT, SOURCE
from ai_service.model_router import LUNA_MODEL, TERRA_MODEL, model_manifest
from ai_service.orchestration import run_workflow


class OrchestrationTest(unittest.TestCase):
    def test_model_routing_is_deliberate(self):
        manifest = model_manifest()
        self.assertEqual(manifest["research_plan"], LUNA_MODEL)
        self.assertEqual(manifest["evidence_extract"], LUNA_MODEL)
        self.assertEqual(manifest["evidence_verify"], TERRA_MODEL)
        self.assertEqual(manifest["screen_score"], TERRA_MODEL)
        self.assertEqual(manifest["memo_write"], TERRA_MODEL)
        self.assertEqual(manifest["adversary_write"], TERRA_MODEL)
        self.assertEqual(manifest["truth_gap_verify"], TERRA_MODEL)
        self.assertEqual(manifest["verdict_brief"], LUNA_MODEL)

    def test_bounded_workflow_runs_to_optional_brief(self):
        second_source = {**SOURCE, "source_id": "src_second", "url": "https://example.com/product"}
        result = run_workflow(
            {
                "deal": DEAL,
                "documents": [
                    {"source": SOURCE, "page_text": PAGE_TEXT},
                    {"source": second_source, "page_text": PAGE_TEXT},
                ],
                "include_verdict_brief": True,
            }
        )
        self.assertIn("research_plan", result)
        self.assertIn("evidence", result)
        self.assertIn("evidence_validation", result)
        self.assertIn("screening", result)
        self.assertIn("memo", result)
        self.assertIn("adversary_report", result)
        self.assertIn("truth_gap_verification", result)
        self.assertIn("verdict_brief", result)
        self.assertTrue(any("parallel_sources=2" in event for event in result["trace"]))
        self.assertEqual(result["trace"][-1], "verdict_brief:luna:non_authoritative")
        self.assertTrue(result["audit_events"])
        self.assertTrue(all("chain-of-thought" not in str(event) for event in result["audit_events"]))


if __name__ == "__main__":
    unittest.main()
