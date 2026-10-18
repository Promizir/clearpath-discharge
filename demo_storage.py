"""Save a workflow, then run again with its ID to read it in a new process."""

import argparse
import asyncio
from pathlib import Path
from uuid import uuid4

from agents import draft_summary
from schemas import DraftRequest, ProposedMedication
from storage import SnapshotStore
from workflow import DischargeWorkflow


DATABASE_PATH = Path(__file__).resolve().parent / "runtime" / "lesson_snapshots.db"


async def main(workflow_id: str | None) -> None:
    store = SnapshotStore(DATABASE_PATH)
    if workflow_id is not None:
        snapshot = store.load(workflow_id)
        if snapshot is None:
            raise SystemExit(f"Workflow {workflow_id} was not found in the lesson database.")
        print("Loaded from:", DATABASE_PATH)
        print(snapshot.model_dump_json(indent=2))
        return

    draft = await draft_summary(DraftRequest(
        patient_id="PT-402",
        doctor_note="Please prepare a discharge draft for review.",
        proposed_medications=[ProposedMedication(name="Amoxicillin")],
    ))
    workflow = DischargeWorkflow(draft)
    workflow.approve(expected_revision=1)  # Simulated doctor action.
    snapshot = await workflow.run_checks(expected_revision=1)
    workflow_id = str(uuid4())
    store.save(workflow_id, snapshot)
    print("Saved workflow:", workflow_id)
    print("Database:", DATABASE_PATH)
    print("This process can now exit. Read the saved snapshot with:")
    print(f".\\.venv\\Scripts\\python.exe demo_storage.py {workflow_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow_id", nargs="?", help="Load this saved workflow instead of creating one.")
    asyncio.run(main(parser.parse_args().workflow_id))
