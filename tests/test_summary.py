"""Verify that mock drafts preserve sources and never approve themselves."""

import unittest

from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from agents import draft_summary
from mcp_server import EHR_PATH
from schemas import DraftRequest, ProposedMedication, load_patient_record


class SummaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_draft_preserves_sources_without_approving(self):
        before = EHR_PATH.read_bytes()
        source = load_patient_record(EHR_PATH)
        request = DraftRequest(
            patient_id="PT-402",
            doctor_note="Keep this clinician note verbatim.",
            proposed_medications=[ProposedMedication(name="Amoxicillin")],
        )
        draft = await draft_summary(request)
        self.assertEqual(draft.patient_id, source.patient_id)
        self.assertEqual(draft.patient_name, source.patient.name)
        self.assertEqual(draft.encounter, source.encounter)
        self.assertEqual(draft.doctor_note, request.doctor_note)
        self.assertEqual(draft.proposed_medications, request.proposed_medications)
        self.assertEqual(draft.status, "AWAITING_DOCTOR_REVIEW")
        self.assertEqual(draft.generation_mode, "MOCK")
        request.proposed_medications[0].name = "Changed later"
        self.assertEqual(draft.proposed_medications[0].name, "Amoxicillin")
        self.assertEqual(before, EHR_PATH.read_bytes())

    async def test_unknown_patient_cannot_get_a_draft(self):
        request = DraftRequest(
            patient_id="PT-999", doctor_note="Review requested.", proposed_medications=[]
        )
        with self.assertRaises(ToolError):
            await draft_summary(request)

    def test_blank_note_is_rejected(self):
        with self.assertRaises(ValidationError):
            DraftRequest(patient_id="PT-402", doctor_note="  ", proposed_medications=[])


if __name__ == "__main__":
    unittest.main()
