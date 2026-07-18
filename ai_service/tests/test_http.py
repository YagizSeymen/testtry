import json
import threading
import unittest
from urllib.request import Request, urlopen

from ai_service import core
from ai_service.examples.sample_payload import DEAL, PAGE_TEXT, SOURCE
from ai_service.server import create_server


class HttpPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server(port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        host, port = cls.server.server_address
        cls.base_url = f"http://{host}:{port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def post(self, path, payload):
        request = Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 200)
            return json.loads(response.read().decode("utf-8"))

    def get(self, path):
        with urlopen(self.base_url + path, timeout=5) as response:
            self.assertEqual(response.status, 200)
            return json.loads(response.read().decode("utf-8"))

    def test_all_contract_endpoints(self):
        health = self.get("/health")
        self.assertEqual(health["runtime_mode"], "deterministic")
        self.assertEqual(health["model_by_stage"]["memo_write"], "gpt-5.6-terra")

        sourcing_plan = self.post(
            "/v1/ai/sourcing/plan",
            {"thesis": "Technical founders in Europe building AI infrastructure with product traction."},
        )
        discovery = self.post(
            "/v1/ai/sourcing/discover",
            {
                "sourcing_plan": sourcing_plan,
                "candidate_documents": [
                    {
                        "candidate": {"company_name": "Acme AI", "founder_names": ["Ada Founder"]},
                        "source": SOURCE,
                        "page_text": PAGE_TEXT,
                    }
                ],
            },
        )
        ranking = self.post("/v1/ai/sourcing/rank", {"discovery": discovery})
        self.assertIn("ranked_candidates", ranking)
        sourcing_run = self.post(
            "/v1/ai/sourcing/run",
            {
                "thesis": "Technical founders in Europe building AI infrastructure with product traction.",
                "candidate_documents": [
                    {
                        "candidate": {"company_name": "Acme AI", "founder_names": ["Ada Founder"]},
                        "source": SOURCE,
                        "page_text": PAGE_TEXT,
                    }
                ],
            },
        )
        self.assertIn("ranking", sourcing_run)
        self.assertTrue(sourcing_run["audit_events"])
        resolved = self.post(
            "/v1/ai/founders/memory/resolve",
            {"founder_name": "Ada Founder", "aliases": ["Ada F."]},
        )
        self.assertEqual(resolved["resolution_confidence"], "medium")
        profile = self.post("/v1/ai/founders/memory/get", {"founder_name": "Ada Founder"})
        self.assertIn("founder_score", profile)

        plan = self.post("/v1/ai/research/plan", {"deal": DEAL})
        self.assertIn("queries", plan)

        extracted = self.post(
            "/v1/ai/evidence/extract",
            {"deal": DEAL, "source": SOURCE, "page_text": PAGE_TEXT},
        )
        evidence = extracted["evidence"]
        validation = self.post("/v1/ai/evidence/verify", {"deal": DEAL, "evidence": evidence})
        evidence = validation["evidence"]

        screening = self.post("/v1/ai/screen/score", {"deal": DEAL, "evidence": evidence})
        self.assertIn(screening["weakest_axis"], core.SCREENING_AXES)
        self.assertIn(screening["weakest_opportunity_axis"], core.OPPORTUNITY_AXES)

        memo = self.post(
            "/v1/ai/memo/write",
            {"deal": DEAL, "evidence": evidence, "screening": screening},
        )
        adversary = self.post(
            "/v1/ai/adversary/write",
            {"deal": DEAL, "evidence": evidence, "screening": screening, "memo": memo},
        )
        verification = self.post(
            "/v1/ai/truth-gap/verify",
            {"deal": DEAL, "evidence": evidence, "memo": memo, "adversary_report": adversary},
        )
        brief = self.post(
            "/v1/ai/verdict/brief",
            {
                "deal": DEAL,
                "evidence": evidence,
                "screening": screening,
                "memo": memo,
                "adversary_report": adversary,
                "truth_gap_verification": verification,
            },
        )
        self.assertIn("summary", brief)


if __name__ == "__main__":
    unittest.main()
