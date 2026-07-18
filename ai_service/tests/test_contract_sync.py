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
        self.assertEqual(contract["contract_version"], "0.4.0")
        self.assertTrue(
            all(endpoint.get("request_schema") for endpoint in contract["ai_service_api"]["endpoints"])
        )
        self.assertTrue(
            all(endpoint.get("response_schema") for endpoint in contract["ai_service_api"]["endpoints"])
        )

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
