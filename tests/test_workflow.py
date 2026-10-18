"""Exercise approval gates and revisions without requiring MCP or an AI model."""

import unittest

from pydantic import ValidationError

from schemas import DischargeSummaryDraft, Encounter
from workflow import DischargeWorkflow


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.draft = DischargeSummaryDraft(
            patient_id="PT-402",
            patient_name="Synthetic Patient",
            encounter=Encounter(primary_diagnosis="Demo", procedure_performed="Demo"),
            doctor_note="Original note.",
            proposed_medications=[],
        )
        self.workflow = DischargeWorkflow(self.draft)

    def test_approval_unlocks_current_draft(self):
        with self.assertRaises(ValueError):
            self.workflow.get_approved_draft()
        self.workflow.approve(expected_revision=1)
        self.assertEqual(self.workflow.get_approved_draft().status, "DOCTOR_APPROVED")

    def test_edit_invalidates_approval_and_rejects_stale_actions(self):
        self.workflow.approve(expected_revision=1)
        state = self.workflow.revise_note("Revised note.", expected_revision=1)
        self.assertEqual(state.revision, 2)
        self.assertEqual(state.draft.status, "AWAITING_DOCTOR_REVIEW")
        with self.assertRaises(ValueError):
            self.workflow.approve(expected_revision=1)
        with self.assertRaises(ValueError):
            self.workflow.revise_note("Stale edit.", expected_revision=1)
        with self.assertRaises(ValueError):
            self.workflow.get_approved_draft()
        self.assertEqual(self.workflow.snapshot(), state)
        self.workflow.approve(expected_revision=2)
        self.assertEqual(self.workflow.get_approved_draft().doctor_note, "Revised note.")

    def test_invalid_edit_leaves_state_unchanged(self):
        self.workflow.approve(expected_revision=1)
        before = self.workflow.snapshot()
        with self.assertRaises(ValidationError):
            self.workflow.revise_note("   ", expected_revision=1)
        self.assertEqual(self.workflow.snapshot(), before)

    def test_note_edit_discards_summary_from_previous_note(self):
        self.draft.clinical_summary = "Generated from the original note."
        self.draft.review_notes = ["Old review note"]
        self.draft.generation_mode = "AMD"
        self.draft.model_name = "test-model"
        self.draft.inference_ms = 123
        workflow = DischargeWorkflow(self.draft)
        workflow.approve(1)
        revised = workflow.revise_note("A changed source note.", 1).draft
        self.assertIsNone(revised.clinical_summary)
        self.assertEqual(revised.review_notes, [])
        self.assertIsNone(revised.model_name)
        self.assertIsNone(revised.inference_ms)
        self.assertEqual(revised.generation_mode, "MOCK")

    def test_external_copies_cannot_change_workflow(self):
        self.draft.doctor_note = "Changed original."
        snapshot = self.workflow.snapshot()
        snapshot.draft.status = "DOCTOR_APPROVED"
        snapshot.draft.encounter.primary_diagnosis = "Changed snapshot."
        with self.assertRaises(ValueError):
            self.workflow.get_approved_draft()
        self.workflow.approve(expected_revision=1)
        returned = self.workflow.get_approved_draft()
        returned.doctor_note = "Changed returned copy."
        self.assertEqual(self.workflow.get_approved_draft().doctor_note, "Original note.")
        self.assertEqual(self.workflow.snapshot().draft.encounter.primary_diagnosis, "Demo")

    def test_new_workflow_does_not_trust_supplied_approval(self):
        self.draft.status = "DOCTOR_APPROVED"
        workflow = DischargeWorkflow(self.draft)
        with self.assertRaises(ValueError):
            workflow.get_approved_draft()


if __name__ == "__main__":
    unittest.main()
