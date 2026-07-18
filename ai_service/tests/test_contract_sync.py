import json
from pathlib import Path
import unittest

from ai_service.server import ROUTES


class ContractSyncTest(unittest.TestCase):
    @staticmethod
    def _refs(value):
        if isinstance(value, dict):
            if isinstance(value.get("$ref"), str):
                yield value["$ref"]
            for item in value.values():
                yield from ContractSyncTest._refs(item)
        elif isinstance(value, list):
            for item in value:
                yield from ContractSyncTest._refs(item)

    def test_every_documented_ai_endpoint_has_a_handler(self):
        root = Path(__file__).resolve().parents[2]
        contract = json.loads((root / "api-contract.json").read_text(encoding="utf-8"))
        documented = {
            f"{contract['ai_service_api']['base_path']}{endpoint['path']}"
            for endpoint in contract["ai_service_api"]["endpoints"]
        }
        self.assertTrue(documented <= set(ROUTES))
        self.assertEqual(contract["contract_version"], "1.0.0")
        self.assertTrue(
            all(endpoint.get("request_schema") for endpoint in contract["ai_service_api"]["endpoints"])
        )
        self.assertTrue(
            all(endpoint.get("response_schema") for endpoint in contract["ai_service_api"]["endpoints"])
        )

    def test_product_routes_match_steps_build_contract(self):
        root = Path(__file__).resolve().parents[2]
        contract = json.loads((root / "api-contract.json").read_text(encoding="utf-8"))
        documented = {
            f"{endpoint['method']} {contract['product_api']['base_path']}{endpoint['path']}"
            for endpoint in contract["product_api"]["endpoints"]
        }
        expected = {
            "POST /api/thesis",
            "GET /api/thesis",
            "POST /api/scan/run",
            "GET /api/dashboard",
            "POST /api/query",
            "GET /api/founders/{id}",
            "POST /api/founders/{id}/activate",
            "POST /api/applications",
            "GET /api/applications/{id}",
            "POST /api/applications/{id}/screen",
            "POST /api/applications/{id}/diligence",
            "POST /api/applications/{id}/memo",
            "POST /api/applications/{id}/adversary",
            "GET /api/decisions/queue",
            "POST /api/decisions/{id}/decide",
            "GET /api/audit?founder_id=",
            "GET /api/metrics",
        }
        self.assertEqual(documented, expected)
        self.assertEqual(contract["product_api"]["owner"], "backend")

    def test_internal_schema_references_resolve(self):
        root = Path(__file__).resolve().parents[2]
        contract = json.loads((root / "api-contract.json").read_text(encoding="utf-8"))
        for reference in self._refs(contract):
            if not reference.startswith("#/"):
                continue
            target = contract
            for part in reference[2:].split("/"):
                self.assertIn(part, target, reference)
                target = target[part]


if __name__ == "__main__":
    unittest.main()
