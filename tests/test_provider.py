"""Exercise the real HTTP boundary without spending tokens or needing credentials."""

import json
from pathlib import Path
import unittest
from unittest.mock import patch

import httpx

from config import public_inference_settings
from providers import InferenceError, generate_summary
from schemas import DraftRequest, PatientRecord


SETTINGS = {"provider": "AMD", "base_url": "https://example.test/v1", "model": "test-model", "api_key": "secret-test-value"}


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.record = PatientRecord.model_validate_json(
            (Path(__file__).resolve().parents[1] / "mock_ehr.json").read_text(encoding="utf-8")
        )
        self.request = DraftRequest(patient_id="PT-402", doctor_note="Source note", proposed_medications=[], use_ai=True)

    async def call_with(self, handler):
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with patch("providers.inference_settings", return_value=SETTINGS), patch("providers.httpx.AsyncClient", return_value=client):
            return await generate_summary(self.record, self.request)

    async def test_valid_output_and_request_boundary(self):
        def handler(request):
            self.assertEqual(str(request.url), "https://example.test/v1/chat/completions")
            self.assertEqual(request.headers["Authorization"], "Bearer secret-test-value")
            payload = json.loads(request.content)
            self.assertEqual(payload["model"], "test-model")
            self.assertEqual(json.loads(payload["messages"][1]["content"])["doctor_note"], "Source note")
            content = json.dumps({"clinical_summary": "A draft for review.", "review_notes": ["Review source evidence."]})
            return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
        summary, model, elapsed = await self.call_with(handler)
        self.assertEqual(summary.clinical_summary, "A draft for review.")
        self.assertEqual(model, "test-model")
        self.assertGreaterEqual(elapsed, 0)

    async def test_invalid_response_does_not_fall_back_to_mock(self):
        for content in ("not json", '{"clinical_summary":"invented", "extra":1}', "```", "{}"):
            with self.subTest(content=content), self.assertRaises(InferenceError):
                await self.call_with(lambda request: httpx.Response(200, json={"choices": [{"message": {"content": content}}]}))

    async def test_provider_error_does_not_expose_response_body(self):
        with self.assertRaises(InferenceError) as caught:
            await self.call_with(lambda request: httpx.Response(401, text="secret-test-value"))
        self.assertIn("401", str(caught.exception))
        self.assertNotIn("secret-test-value", str(caught.exception))

    async def test_timeout_has_clear_error(self):
        def handler(request):
            raise httpx.ReadTimeout("secret-test-value", request=request)
        with self.assertRaises(InferenceError) as caught:
            await self.call_with(handler)
        self.assertIn("timeout", str(caught.exception))
        self.assertNotIn("secret-test-value", str(caught.exception))

    async def test_unconfigured_request_cannot_claim_amd(self):
        with patch("providers.inference_settings", return_value={**SETTINGS, "api_key": ""}), self.assertRaises(InferenceError):
            await generate_summary(self.record, self.request)

    def test_public_configuration_never_returns_credentials(self):
        with patch("config.inference_settings", return_value=SETTINGS):
            public = public_inference_settings()
        self.assertTrue(public["configured"])
        self.assertNotIn("secret-test-value", json.dumps(public))
        self.assertNotIn("base_url", public)
