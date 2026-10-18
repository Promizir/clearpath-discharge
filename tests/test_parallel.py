"""Test concurrent scheduling and failure handling without timing assumptions."""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from schemas import BillingCheckResult, DischargeSummaryDraft, Encounter, PharmacyCheckResult, ProposedMedication
from workflow import DischargeWorkflow


class ParallelTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.workflow = DischargeWorkflow(DischargeSummaryDraft(
            patient_id="PT-402", patient_name="Demo",
            encounter=Encounter(primary_diagnosis="Demo", procedure_performed="Demo"),
            doctor_note="Review requested.",
            proposed_medications=[ProposedMedication(name="Amoxicillin")],
        ))
        self.pharmacy = PharmacyCheckResult(patient_id="PT-402", status="NO_DEMO_RULE_MATCH", flags=[])
        self.billing = BillingCheckResult(patient_id="PT-402", status="QUANTITIES_MATCH", discrepancies=[])

    async def test_real_workers_complete_with_findings(self):
        self.workflow.approve(expected_revision=1)
        state = await self.workflow.run_checks(expected_revision=1)
        self.assertEqual(state.parallel_status, "COMPLETED")
        self.assertEqual(state.pharmacy_result.status, "FLAGGED")
        self.assertEqual(state.billing_result.status, "DISCREPANCIES_FOUND")
        self.assertEqual(state.check_errors, {})
        edited = self.workflow.revise_note("Edited.", expected_revision=1)
        self.assertIsNone(edited.pharmacy_result)
        self.assertIsNone(edited.billing_result)
        self.assertEqual(edited.parallel_status, "NOT_STARTED")

    async def test_both_workers_start_before_either_finishes(self):
        self.workflow.approve(expected_revision=1)
        pharmacy_started = asyncio.Event()
        billing_started = asyncio.Event()

        async def pharmacy(draft):
            pharmacy_started.set()
            await billing_started.wait()
            return self.pharmacy

        async def billing(patient_id):
            billing_started.set()
            await pharmacy_started.wait()
            return self.billing

        with patch("workflow.check_pharmacy", side_effect=pharmacy), patch("workflow.check_billing", side_effect=billing):
            state = await asyncio.wait_for(self.workflow.run_checks(1), timeout=5)
        self.assertEqual(state.parallel_status, "COMPLETED")

    async def test_partial_failure_preserves_success_and_retry_clears_errors(self):
        self.workflow.approve(expected_revision=1)
        with patch("workflow.check_billing", side_effect=RuntimeError("Demo billing outage")):
            state = await self.workflow.run_checks(1)
        self.assertEqual(state.parallel_status, "FAILED")
        self.assertEqual(state.pharmacy_result.status, "FLAGGED")
        self.assertIsNone(state.billing_result)
        self.assertEqual(state.check_errors, {"billing": "Demo billing outage"})
        retried = await self.workflow.run_checks(1)
        self.assertEqual(retried.parallel_status, "COMPLETED")
        self.assertEqual(retried.check_errors, {})

    async def test_approval_required_before_scheduling(self):
        with patch("workflow.check_pharmacy", new_callable=AsyncMock) as pharmacy, patch("workflow.check_billing", new_callable=AsyncMock) as billing:
            with self.assertRaises(ValueError):
                await self.workflow.run_checks(1)
            pharmacy.assert_not_awaited()
            billing.assert_not_awaited()

    async def test_edit_while_running_rejects_batch_and_duplicate_calls(self):
        self.workflow.approve(expected_revision=1)
        entered = asyncio.Event()
        release = asyncio.Event()

        async def delayed_billing(patient_id):
            entered.set()
            await release.wait()
            return self.billing

        with patch("workflow.check_billing", side_effect=delayed_billing):
            task = asyncio.create_task(self.workflow.run_checks(1))
            try:
                await asyncio.wait_for(entered.wait(), 5)
                self.assertEqual(self.workflow.snapshot().parallel_status, "RUNNING")
                with self.assertRaisesRegex(ValueError, "already running"):
                    await self.workflow.run_checks(1)
                with self.assertRaisesRegex(ValueError, "already running"):
                    await self.workflow.run_pharmacy(1)
                self.workflow.revise_note("Changed while running.", 1)
            finally:
                release.set()
                with self.assertRaisesRegex(ValueError, "Stale revision"):
                    await asyncio.wait_for(task, 5)
        state = self.workflow.snapshot()
        self.assertEqual(state.parallel_status, "NOT_STARTED")
        self.assertIsNone(state.pharmacy_result)
        self.assertIsNone(state.billing_result)

    async def test_cancelled_batch_can_retry(self):
        self.workflow.approve(expected_revision=1)
        entered = asyncio.Event()

        async def waiting_billing(patient_id):
            entered.set()
            await asyncio.Event().wait()

        with patch("workflow.check_billing", side_effect=waiting_billing):
            task = asyncio.create_task(self.workflow.run_checks(1))
            try:
                await asyncio.wait_for(entered.wait(), 5)
            finally:
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
        self.assertEqual(self.workflow.snapshot().parallel_status, "CANCELLED")
        self.assertIsNone(self.workflow.snapshot().pharmacy_result)
        self.assertEqual((await self.workflow.run_checks(1)).parallel_status, "COMPLETED")

    async def test_wrong_patient_result_is_a_worker_failure(self):
        self.workflow.approve(expected_revision=1)
        self.billing.patient_id = "PT-999"
        with patch("workflow.check_billing", return_value=self.billing):
            state = await self.workflow.run_checks(1)
        self.assertEqual(state.parallel_status, "FAILED")
        self.assertIn("billing", state.check_errors)
        self.assertIsNone(state.billing_result)
        self.assertIsNotNone(state.pharmacy_result)


if __name__ == "__main__":
    unittest.main()
