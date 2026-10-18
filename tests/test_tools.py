"""Check actual MCP calls, including errors and the limits of our demo rule."""

import unittest

from fastmcp import Client

from mcp_server import EHR_PATH, mcp
from schemas import PharmacyCheckResult


class PharmacyToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_conflict_and_normalized_names(self):
        before = EHR_PATH.read_bytes()
        async with Client(mcp) as client:
            for name in ("Amoxicillin", "  AMOXICILLIN  "):
                with self.subTest(name=name):
                    result = await client.call_tool(
                        "check_pharmacy_safety",
                        {"patient_id": "PT-402", "prescribed_meds": [{"name": name}]},
                    )
                    check = PharmacyCheckResult.model_validate(result.structured_content)
                    self.assertEqual(check.status, "FLAGGED")
                    self.assertEqual(len(check.flags), 1)
                    self.assertEqual(check.flags[0].matched_allergy, "Penicillin")
                    self.assertTrue(check.review_required)
        self.assertEqual(before, EHR_PATH.read_bytes())

    async def test_unrecognized_medicine_does_not_grant_clearance(self):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "check_pharmacy_safety",
                {"patient_id": "PT-402", "prescribed_meds": [{"name": "Unknown medicine"}]},
            )
        check = PharmacyCheckResult.model_validate(result.structured_content)
        self.assertEqual(check.status, "NO_DEMO_RULE_MATCH")
        self.assertEqual(check.flags, [])
        self.assertTrue(check.review_required)

    async def test_invalid_requests_are_errors(self):
        cases = [
            {"patient_id": "PT-999", "prescribed_meds": [{"name": "Amoxicillin"}]},
            {"patient_id": "PT-402", "prescribed_meds": []},
            {"patient_id": "PT-402", "prescribed_meds": [{"name": "   "}]},
            {"patient_id": "PT-402", "prescribed_meds": [{"name": 123}]},
            {"patient_id": "PT-402", "prescribed_meds": [{"nmae": "Amoxicillin"}]},
            {"patient_id": "PT-402"},
        ]
        async with Client(mcp) as client:
            for arguments in cases:
                with self.subTest(arguments=arguments):
                    result = await client.call_tool(
                        "check_pharmacy_safety", arguments, raise_on_error=False
                    )
                    self.assertTrue(result.is_error)


if __name__ == "__main__":
    unittest.main()
