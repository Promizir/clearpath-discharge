"""Verify approval and revision checks around an asynchronous worker."""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from schemas import DischargeSummaryDraft, Encounter, PharmacyCheckResult, ProposedMedication
from workflow import DischargeWorkflow


class PharmacyWorkflowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.workflow = DischargeWorkflow(
            DischargeSummaryDraft(
                patient_id="PT-402", patient_name="Synthetic Patient",
                encounter=Encounter(primary_diagnosis="Demo", procedure_performed="Demo"),
                doctor_note="Review requested.",
                proposed_medications=[ProposedMedication(name="Amoxicillin")],
            )
        )

    async def test_unapproved_draft_never_calls_worker(self):
        with patch("workflow.check_pharmacy", new_callable=AsyncMock) as worker:
            with self.assertRaises(ValueError):
                await self.workflow.run_pharmacy(expected_revision=1)
            worker.assert_not_awaited()

    async def test_real_tool_finding_is_saved_and_cleared_on_edit(self):
        self.workflow.approve(expected_revision=1)
        state = await self.workflow.run_pharmacy(expected_revision=1)
        self.assertEqual(state.pharmacy_result.status, "FLAGGED")
        self.assertTrue(state.pharmacy_result.review_required)
        state.pharmacy_result.flags.clear()
        self.assertEqual(len(self.workflow.snapshot().pharmacy_result.flags), 1)
        revised = self.workflow.revise_note("Edited note.", expected_revision=1)
        self.assertIsNone(revised.pharmacy_result)

    async def test_edit_during_worker_rejects_old_result_and_duplicate_run(self):
        self.workflow.approve(expected_revision=1)
        entered = asyncio.Event()
        release = asyncio.Event()

        async def delayed_worker(draft):
            entered.set()
            await release.wait()
            return PharmacyCheckResult(patient_id=draft.patient_id, status="NO_DEMO_RULE_MATCH", flags=[])

        with patch("workflow.check_pharmacy", side_effect=delayed_worker):
            task = asyncio.create_task(self.workflow.run_pharmacy(expected_revision=1))
            try:
                await asyncio.wait_for(entered.wait(), timeout=5)
                with self.assertRaisesRegex(ValueError, "already running"):
                    await self.workflow.run_pharmacy(expected_revision=1)
                self.workflow.revise_note("Changed while waiting.", expected_revision=1)
                self.workflow.approve(expected_revision=2)
            finally:
                release.set()
                with self.assertRaisesRegex(ValueError, "Stale revision"):
                    await asyncio.wait_for(task, timeout=5)

        self.assertIsNone(self.workflow.snapshot().pharmacy_result)
        # The running flag must have reset after the rejected result.
        state = await self.workflow.run_pharmacy(expected_revision=2)
        self.assertEqual(state.pharmacy_result.status, "FLAGGED")

    async def test_worker_failure_clears_old_result_and_allows_retry(self):
        self.workflow.approve(expected_revision=1)
        await self.workflow.run_pharmacy(expected_revision=1)
        with patch("workflow.check_pharmacy", side_effect=RuntimeError("Demo outage")):
            with self.assertRaises(RuntimeError):
                await self.workflow.run_pharmacy(expected_revision=1)
        self.assertIsNone(self.workflow.snapshot().pharmacy_result)
        state = await self.workflow.run_pharmacy(expected_revision=1)
        self.assertEqual(state.pharmacy_result.status, "FLAGGED")

    async def test_wrong_patient_result_is_rejected(self):
        self.workflow.approve(expected_revision=1)
        wrong = PharmacyCheckResult(patient_id="PT-999", status="NO_DEMO_RULE_MATCH", flags=[])
        with patch("workflow.check_pharmacy", return_value=wrong):
            with self.assertRaisesRegex(ValueError, "different patient"):
                await self.workflow.run_pharmacy(expected_revision=1)
        self.assertIsNone(self.workflow.snapshot().pharmacy_result)


if __name__ == "__main__":
    unittest.main()
