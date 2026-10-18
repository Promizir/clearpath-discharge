"""Check persistence at the worker boundary, including failed database writes."""

import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

from schemas import BillingCheckResult, DischargeSummaryDraft, Encounter, ProposedMedication
from storage import SnapshotStore
from workflow import DischargeWorkflow


class PersistentWorkflowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.store = SnapshotStore(Path(directory) / "workflow.db")
        self.workflow = DischargeWorkflow(
            DischargeSummaryDraft(
                patient_id="PT-402", patient_name="Demo",
                encounter=Encounter(primary_diagnosis="Demo", procedure_performed="Demo"),
                doctor_note="Review requested.",
                proposed_medications=[ProposedMedication(name="Amoxicillin")],
            ),
            on_change=lambda snapshot: self.store.save("workflow-1", snapshot),
        )
        self.workflow.approve(1)

    async def test_running_is_saved_before_worker_and_final_results_afterwards(self):
        async def billing(patient_id):
            stored = self.store.load("workflow-1")
            self.assertEqual(stored.parallel_status, "RUNNING")
            self.assertIsNone(stored.pharmacy_result)
            self.assertIsNone(stored.billing_result)
            return BillingCheckResult(patient_id=patient_id, status="QUANTITIES_MATCH", discrepancies=[])

        with patch("workflow.check_billing", side_effect=billing):
            completed = await self.workflow.run_checks(1)
        self.assertEqual(self.store.load("workflow-1"), completed)

    async def test_start_save_failure_prevents_workers_and_allows_retry(self):
        before = self.workflow.snapshot()
        with patch.object(self.store, "save", side_effect=sqlite3.OperationalError("Demo failure")), patch("workflow.check_pharmacy", new_callable=AsyncMock) as pharmacy, patch("workflow.check_billing", new_callable=AsyncMock) as billing:
            with self.assertRaises(sqlite3.OperationalError):
                await self.workflow.run_checks(1)
            pharmacy.assert_not_awaited()
            billing.assert_not_awaited()
        self.assertEqual(self.workflow.snapshot(), before)
        self.assertEqual(self.store.load("workflow-1"), before)
        self.assertEqual((await self.workflow.run_checks(1)).parallel_status, "COMPLETED")


if __name__ == "__main__":
    unittest.main()
