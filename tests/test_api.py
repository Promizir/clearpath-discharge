"""Exercise HTTP validation and workflow rules through an in-process client."""

import unittest
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import create_app
from storage import SnapshotStore
from providers import InferenceError


class ApiTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.database_path = Path(directory) / "api.db"
        self.client = self.enterContext(TestClient(create_app(self.database_path)))
        self.body = {
            "patient_id": "PT-402",
            "doctor_note": "Please prepare a draft for review.",
            "proposed_medications": [{"name": "Amoxicillin"}],
        }

    def create_workflow(self):
        response = self.client.post("/workflows", json=self.body)
        self.assertEqual(response.status_code, 201, response.text)
        return "/workflows/" + response.json()["workflow_id"]

    def test_public_demo_limits_failed_model_attempts(self):
        with patch("main.draft_summary", side_effect=InferenceError("Test provider error")) as generate:
            for _ in range(30):
                response = self.client.post("/workflows", json={**self.body, "use_ai": True})
                self.assertEqual(response.status_code, 502)
            response = self.client.post("/workflows", json={**self.body, "use_ai": True})
            self.assertEqual(response.status_code, 429)
            self.assertEqual(generate.call_count, 30)

    def test_oversized_input_is_rejected_before_generation(self):
        with patch("main.draft_summary") as generate:
            response = self.client.post("/workflows", json={**self.body, "doctor_note": "x" * 10001})
            self.assertEqual(response.status_code, 422)
            generate.assert_not_called()

    def test_full_http_flow_and_edit_invalidation(self):
        path = self.create_workflow()
        self.assertEqual(self.client.post(path + "/checks", json={"expected_revision": 1}).status_code, 409)
        self.assertEqual(self.client.post(path + "/approve", json={"expected_revision": 1}).status_code, 200)
        response = self.client.post(path + "/checks", json={"expected_revision": 1})
        self.assertEqual(response.status_code, 200)
        state = response.json()["snapshot"]
        self.assertEqual(state["parallel_status"], "COMPLETED")
        self.assertEqual(state["pharmacy_result"]["status"], "FLAGGED")
        self.assertEqual(state["billing_result"]["status"], "DISCREPANCIES_FOUND")
        self.assertEqual(self.client.get(path).json()["snapshot"], state)
        edited = self.client.patch(path + "/note", json={"expected_revision": 1, "doctor_note": "Edited note."})
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.json()["snapshot"]["revision"], 2)
        self.assertIsNone(edited.json()["snapshot"]["pharmacy_result"])
        self.assertIsNone(edited.json()["snapshot"]["billing_result"])
        self.assertEqual(self.client.post(path + "/approve", json={"expected_revision": 1}).status_code, 409)

    def test_invalid_input_returns_422_without_changing_state(self):
        path = self.create_workflow()
        before = self.client.get(path).json()
        for body in ({"expected_revision": "1"}, {"expected_revision": True}, {"expected_revision": 0}, {}):
            with self.subTest(body=body):
                self.assertEqual(self.client.post(path + "/approve", json=body).status_code, 422)
        self.assertEqual(self.client.patch(path + "/note", json={"expected_revision": 1, "doctor_note": "  "}).status_code, 422)
        self.assertEqual(self.client.get(path).json(), before)
        self.assertEqual(self.client.post("/workflows", json={}).status_code, 422)

    def test_unknown_workflow_and_patient(self):
        self.assertEqual(self.client.get("/workflows/missing").status_code, 404)
        self.body["patient_id"] = "PT-999"
        self.assertEqual(self.client.post("/workflows", json=self.body).status_code, 502)

    def test_worker_failure_is_visible_in_response(self):
        path = self.create_workflow()
        self.client.post(path + "/approve", json={"expected_revision": 1})
        with patch("workflow.check_billing", side_effect=RuntimeError("Demo outage")):
            response = self.client.post(path + "/checks", json={"expected_revision": 1})
        self.assertEqual(response.status_code, 200)
        state = response.json()["snapshot"]
        self.assertEqual(state["parallel_status"], "FAILED")
        self.assertEqual(state["check_errors"], {"billing": "Demo outage"})
        self.assertIsNotNone(state["pharmacy_result"])

    def test_workflows_are_independent_and_docs_exist(self):
        first, second = self.create_workflow(), self.create_workflow()
        self.assertNotEqual(first, second)
        self.client.post(first + "/approve", json={"expected_revision": 1})
        self.assertEqual(self.client.get(second).json()["snapshot"]["draft"]["status"], "AWAITING_DOCTOR_REVIEW")
        self.assertEqual(self.client.get("/docs").status_code, 200)
        self.assertIn("/workflows/{workflow_id}/checks", self.client.get("/openapi.json").json()["paths"])

    def test_new_app_restores_completed_workflow_and_can_edit_it(self):
        path = self.create_workflow()
        self.client.post(path + "/approve", json={"expected_revision": 1})
        expected = self.client.post(path + "/checks", json={"expected_revision": 1}).json()
        with TestClient(create_app(self.database_path)) as restarted:
            response = restarted.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), expected)
            edited = restarted.patch(path + "/note", json={"expected_revision": 1, "doctor_note": "Edit after restart."})
            self.assertEqual(edited.status_code, 200)
        with TestClient(create_app(self.database_path)) as restarted_again:
            restored = restarted_again.get(path).json()["snapshot"]
            self.assertEqual(restored["revision"], 2)
            self.assertEqual(restored["draft"]["status"], "AWAITING_DOCTOR_REVIEW")
            self.assertIsNone(restored["pharmacy_result"])
            self.assertIsNone(restored["billing_result"])

    def test_interrupted_checks_restore_as_failed_and_can_retry(self):
        path = self.create_workflow()
        self.client.post(path + "/approve", json={"expected_revision": 1})
        workflow_id = path.rsplit("/", 1)[1]
        store = SnapshotStore(self.database_path)
        interrupted = store.load(workflow_id)
        interrupted.parallel_status = "RUNNING"
        store.save(workflow_id, interrupted)
        with TestClient(create_app(self.database_path)) as restarted:
            restored = restarted.get(path).json()["snapshot"]
            self.assertEqual(restored["parallel_status"], "FAILED")
            self.assertIn("interrupted", restored["check_errors"]["workflow"])
            self.assertEqual(store.load(workflow_id).parallel_status, "FAILED")
            retried = restarted.post(path + "/checks", json={"expected_revision": 1})
            self.assertEqual(retried.status_code, 200)
            self.assertEqual(retried.json()["snapshot"]["parallel_status"], "COMPLETED")

    def test_failed_approval_save_returns_503_and_preserves_previous_state(self):
        path = self.create_workflow()
        before = self.client.get(path).json()
        with patch("storage.SnapshotStore.save", side_effect=sqlite3.OperationalError("Demo locked database")):
            response = self.client.post(path + "/approve", json={"expected_revision": 1})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.client.get(path).json(), before)
        with TestClient(create_app(self.database_path)) as restarted:
            self.assertEqual(restarted.get(path).json(), before)


if __name__ == "__main__":
    unittest.main()
