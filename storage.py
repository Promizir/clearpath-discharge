"""Lesson 10: save validated workflow snapshots in a local SQLite file."""

import sqlite3
from contextlib import closing
from pathlib import Path

from schemas import WorkflowSnapshot


class SnapshotStore:
    def __init__(self, database_path: Path):
        self.database_path = database_path.resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_snapshots (
                    workflow_id TEXT PRIMARY KEY NOT NULL,
                    snapshot_json TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def save(self, workflow_id: str, snapshot: WorkflowSnapshot) -> None:
        """Insert or replace the latest snapshot; this is not a revision history."""
        if not workflow_id.strip():
            raise ValueError("Workflow ID cannot be blank.")
        # Revalidate because callers could have modified a model after creation.
        validated = WorkflowSnapshot.model_validate(snapshot.model_dump())
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                """
                INSERT INTO workflow_snapshots (workflow_id, snapshot_json)
                VALUES (?, ?)
                ON CONFLICT(workflow_id)
                DO UPDATE SET snapshot_json = excluded.snapshot_json
                """,
                (workflow_id, validated.model_dump_json()),
            )
            connection.commit()

    def load(self, workflow_id: str) -> WorkflowSnapshot | None:
        """Return a validated snapshot, or None if the workflow ID is absent."""
        with closing(sqlite3.connect(self.database_path)) as connection:
            row = connection.execute(
                "SELECT snapshot_json FROM workflow_snapshots WHERE workflow_id = ?",
                (workflow_id,),
            ).fetchone()
        if row is None:
            return None
        return WorkflowSnapshot.model_validate_json(row[0])
