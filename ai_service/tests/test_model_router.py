import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from ai_service.model_router import (
    EXTRACT_RESPONSE_SCHEMA,
    ModelProviderError,
    ModelRouter,
    configured_openai_api_key,
)


class ModelRouterTest(unittest.TestCase):
    def test_api_key_is_normalised_for_deployment_dashboard_pastes(self):
        examples = (
            "  test-key\n",
            '"test-key"',
            "OPENAI_API_KEY=test-key",
        )
        for value in examples:
            with self.subTest(value=value), patch.dict(
                os.environ, {"OPENAI_API_KEY": value}, clear=False
            ):
                self.assertEqual(configured_openai_api_key(), "test-key")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test\nkey"}, clear=False)
    def test_api_key_rejects_embedded_newline(self):
        with self.assertRaisesRegex(ModelProviderError, "embedded newline"):
            configured_openai_api_key()

    @patch("openai.OpenAI")
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False)
    def test_extractor_requests_strict_json_schema(self, openai_class):
        client = openai_class.return_value
        client.responses.create.return_value = SimpleNamespace(
            output_text=(
                '{"founder_name":"Maya Chen","claims":['
                '{"claim_id":"clm_001","type":"product",'
                '"text":"NeuralKit shipped a platform.",'
                '"source_span":"NeuralKit shipped a platform."}]}'
            )
        )

        result = ModelRouter(mode="openai").run(
            "extract",
            {"company_name": "NeuralKit", "deck_text": "NeuralKit shipped a platform."},
            lambda _: {},
        )

        self.assertEqual(result["founder_name"], "Maya Chen")
        openai_class.assert_called_once_with(api_key="test-key", timeout=60.0, max_retries=0)
        request = client.responses.create.call_args.kwargs
        self.assertEqual(request["reasoning"], {"effort": "none"})
        response_format = request["text"]["format"]
        self.assertEqual(response_format["type"], "json_schema")
        self.assertTrue(response_format["strict"])
        self.assertEqual(response_format["schema"], EXTRACT_RESPONSE_SCHEMA)


if __name__ == "__main__":
    unittest.main()
