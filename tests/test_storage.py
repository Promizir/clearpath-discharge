"""Use temporary on-disk databases to check persistence and validation."""

import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import ValidationError

from schemas import DischargeSummaryDraft, Encounter, WorkflowSnapshot
from storage import SnapshotStore


class StorageTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.path = Path(directory) / "nested" / "workflows.db"
        self.store = SnapshotStore(self.path)
        self.snapshot = WorkflowSnapshot(
            revision=1,
            draft=DischargeSummaryDraft(
                patient_id="PT-402", patient_name="Synthetic Patient",
                encounter=Encounter(primary_diagnosis="Demo", procedure_performed="Demo"),
                doctor_note="Doctor's note: review requested.", proposed_medications=[],
            ),
        )

    def test_new_store_can_load_committed_snapshot(self):
        self.store.save("workflow-1", self.snapshot)
        reopened = SnapshotStore(self.path)
        loaded = reopened.load("workflow-1")
        self.assertEqual(loaded, self.snapshot)
        loaded.draft.doctor_note = "Edited only in memory."
        self.assertEqual(reopened.load("workflow-1"), self.snapshot)

    def test_save_updates_one_workflow_without_changing_another(self):
        self.store.save("first", self.snapshot)
        self.store.save("second", self.snapshot)
        changed = self.snapshot.model_copy(deep=True)
        changed.revision = 2
        changed.draft.doctor_note = "Updated note."
        self.store.save("first", changed)
        self.assertEqual(self.store.load("first"), changed)
        self.assertEqual(self.store.load("second"), self.snapshot)

    def test_missing_id_and_sql_like_id_are_handled_as_data(self):
        self.assertIsNone(self.store.load("missing"))
        unusual_id = "x'); DROP TABLE workflow_snapshots; --"
        self.store.save(unusual_id, self.snapshot)
        self.assertEqual(self.store.load(unusual_id), self.snapshot)
        self.store.save("normal", self.snapshot)
        self.assertEqual(self.store.load("normal"), self.snapshot)

    def test_invalid_save_does_not_replace_previous_snapshot(self):
        self.store.save("first", self.snapshot)
        broken = self.snapshot.model_copy(deep=True)
        broken.revision = 0
        with self.assertRaises(ValidationError):
            self.store.save("first", broken)
        self.assertEqual(self.store.load("first"), self.snapshot)
        with self.assertRaises(ValueError):
            self.store.save("   ", self.snapshot)

    def test_invalid_stored_data_is_rejected_on_load(self):
        self.store.save("first", self.snapshot)
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute(
                "UPDATE workflow_snapshots SET snapshot_json = ? WHERE workflow_id = ?",
                ('{"revision": 0}', "first"),
            )
            connection.commit()
        with self.assertRaises(ValidationError):
            self.store.load("first")


if __name__ == "__main__":
    unittest.main()
