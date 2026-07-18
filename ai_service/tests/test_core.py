import unittest

from ai_service import core
from ai_service.examples.sample_payload import DEAL, PAGE_TEXT, SOURCE


class CorePipelineTest(unittest.TestCase):
    def test_full_pipeline_matches_contract_shape(self):
        plan = core.endpoint_research_plan({"deal": DEAL})
        self.assertIn("queries", plan)
        self.assertIn("target_urls", plan)
        self.assertIn("research_priorities", plan)

        extracted = core.endpoint_evidence_extract(
            {"deal": DEAL, "source": SOURCE, "page_text": PAGE_TEXT}
        )
        evidence = extracted["evidence"]
        self.assertGreaterEqual(len(evidence), 5)
        self.assertTrue(all("evidence_id" in item for item in evidence))

        screening = core.endpoint_screen_score({"deal": DEAL, "evidence": evidence})
        self.assertEqual(screening["deal_id"], DEAL["deal_id"])
        self.assertIn(screening["weakest_axis"], core.SCREENING_AXES)
        self.assertIn(screening["weakest_opportunity_axis"], core.OPPORTUNITY_AXES)
        self.assertEqual(screening["selected_counter_case_lens"], screening["weakest_axis"])
        self.assertEqual({item["axis"] for item in screening["opportunity_axes"]}, {"founder", "market", "idea_market"})
        self.assertNotIn("overall_score", screening)

        evidence_validation = core.endpoint_evidence_verify({"deal": DEAL, "evidence": evidence})
        evidence = evidence_validation["evidence"]
        self.assertTrue(all("trust_score" in item for item in evidence))

        memo = core.endpoint_memo_write(
            {"deal": DEAL, "evidence": evidence, "screening": screening}
        )
        self.assertIn(memo["recommendation"], {"approve", "reject", "watchlist", "needs_more_research"})
        self.assertTrue(memo["evidence_ids"])

        adversary = core.endpoint_adversary_write(
            {"deal": DEAL, "evidence": evidence, "screening": screening, "memo": memo}
        )
        self.assertEqual(adversary["counter_case_lens"], screening["selected_counter_case_lens"])
        self.assertTrue(adversary["objections"])
        for objection in adversary["objections"]:
            self.assertTrue(objection["evidence_ids"] or objection["is_speculation"])

        verification = core.endpoint_truth_gap_verify(
            {
                "deal": DEAL,
                "evidence": evidence,
                "memo": memo,
                "adversary_report": adversary,
            }
        )
        self.assertEqual(len(verification["checked_objections"]), len(adversary["objections"]))
        for checked in verification["checked_objections"]:
            self.assertIn(checked["badge"], {"verified", "unverified", "speculation"})

        brief = core.endpoint_verdict_brief(
            {
                "deal": DEAL,
                "evidence": evidence,
                "screening": screening,
                "memo": memo,
                "adversary_report": adversary,
                "truth_gap_verification": verification,
            }
        )
        self.assertIn(brief["signal"], {"memo_still_strong", "counter_case_serious", "needs_human_diligence"})
        self.assertIn("human reviewer", brief["summary"])
        self.assertIn("swot", memo)
        self.assertIn("diligence_log", memo)


if __name__ == "__main__":
    unittest.main()
