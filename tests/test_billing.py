"""Exercise billing through the worker and real in-memory MCP calls."""

import unittest
from unittest.mock import patch

from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from agents import check_billing
from mcp_server import EHR_PATH
from schemas import ConsumableQuantity, load_patient_record


class BillingTests(unittest.IsolatedAsyncioTestCase):
    async def test_fixture_finds_missing_quantities_without_writing(self):
        before = EHR_PATH.read_bytes()
        result = await check_billing("PT-402")
        self.assertEqual(result.status, "DISCREPANCIES_FOUND")
        differences = {item.item_id: item.quantity_difference for item in result.discrepancies}
        self.assertEqual(differences, {"HEMOSTATIC_GAUZE": 2, "SKIN_STAPLER": 1})
        self.assertTrue(result.review_required)
        self.assertEqual(before, EHR_PATH.read_bytes())

    async def test_matching_totals_include_repeated_line_items(self):
        record = load_patient_record(EHR_PATH)
        record.billing.billed_consumables = [item.model_copy(deep=True) for item in record.billing.used_consumables]
        record.billing.billed_consumables[0].quantity = 1
        record.billing.billed_consumables.append(ConsumableQuantity(item_id="HEMOSTATIC_GAUZE", quantity=2))
        with patch("mcp_server._get_patient_record", return_value=record):
            result = await check_billing("PT-402")
        self.assertEqual(result.status, "QUANTITIES_MATCH")
        self.assertEqual(result.discrepancies, [])
        self.assertTrue(result.review_required)

    async def test_excess_billing_and_billed_only_items_are_reported(self):
        record = load_patient_record(EHR_PATH)
        record.billing.billed_consumables = [item.model_copy(deep=True) for item in record.billing.used_consumables]
        record.billing.billed_consumables[0].quantity = 5
        record.billing.billed_consumables.append(ConsumableQuantity(item_id="OTHER_ITEM", quantity=1))
        with patch("mcp_server._get_patient_record", return_value=record):
            result = await check_billing("PT-402")
        differences = {item.item_id: item.quantity_difference for item in result.discrepancies}
        self.assertEqual(differences, {"HEMOSTATIC_GAUZE": -2, "OTHER_ITEM": -1})

    async def test_unknown_patient_is_rejected(self):
        with self.assertRaises(ToolError):
            await check_billing("PT-999")

    def test_invalid_quantities_are_rejected(self):
        for quantity in (-1, 0, "3", True):
            with self.subTest(quantity=quantity), self.assertRaises(ValidationError):
                ConsumableQuantity(item_id="HEMOSTATIC_GAUZE", quantity=quantity)


if __name__ == "__main__":
    unittest.main()
