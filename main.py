"""Local HTTP API with SQLite persistence for a single server process."""

import sqlite3
import os
import time
from collections import deque
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastmcp.exceptions import ToolError

from agents import draft_summary
from config import public_inference_settings
from providers import InferenceError
from schemas import DraftRequest, NoteRevisionRequest, RevisionRequest, WorkflowResponse
from storage import SnapshotStore
from workflow import DischargeWorkflow, WorkflowConflict


DEFAULT_DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(Path(__file__).resolve().parent / "runtime" / "discharge.db")))


def create_app(database_path: Path = DEFAULT_DATABASE_PATH) -> FastAPI:
    """Keep live objects in a cache and durable snapshots in the chosen database."""
    app = FastAPI(
        title="ClearPath Discharge Coordination API",
        description="Local synthetic demo. Approval actions are simulated; snapshots persist in SQLite. Use one server process.",
    )
    store = SnapshotStore(database_path)
    workflows: dict[str, DischargeWorkflow] = {}
    # A single-process public demo should not allow unlimited model spending.
    inference_attempts: deque[float] = deque()
    active_inference = 0
    static_path = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=static_path), name="static")

    @app.get("/", include_in_schema=False)
    async def dashboard() -> FileResponse:
        return FileResponse(static_path / "index.html")

    @app.get("/api/config")
    async def public_config() -> dict[str, object]:
        return public_inference_settings()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "app": "ClearPath"}

    @app.exception_handler(InferenceError)
    async def inference_failure(request: Request, error: InferenceError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(error)})

    def get_workflow(workflow_id: str) -> DischargeWorkflow:
        if workflow_id not in workflows:
            snapshot = store.load(workflow_id)
            if snapshot is None:
                raise HTTPException(status_code=404, detail="Workflow not found")
            workflows[workflow_id] = DischargeWorkflow.from_snapshot(
                snapshot, on_change=lambda state: store.save(workflow_id, state)
            )
        return workflows[workflow_id]

    @app.exception_handler(sqlite3.Error)
    async def storage_failure(request: Request, error: sqlite3.Error) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": "Workflow storage is unavailable. Retry the request."},
        )

    @app.exception_handler(WorkflowConflict)
    async def workflow_conflict(request: Request, error: WorkflowConflict) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.exception_handler(ToolError)
    async def tool_failure(request: Request, error: ToolError) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content={"detail": "A required hospital tool could not complete the request. Check the patient ID and tool availability."},
        )

    @app.post("/workflows", response_model=WorkflowResponse, status_code=201)
    async def create_workflow(body: DraftRequest) -> WorkflowResponse:
        nonlocal active_inference
        if body.use_ai:
            now = time.monotonic()
            while inference_attempts and now - inference_attempts[0] >= 3600:
                inference_attempts.popleft()
            if len(inference_attempts) >= 30:
                raise HTTPException(status_code=429, detail="The shared demo's hourly AI request limit has been reached. Try again later.")
            if active_inference >= 2:
                raise HTTPException(status_code=429, detail="Two AI drafts are already being prepared. Please retry shortly.")
            inference_attempts.append(now)
            active_inference += 1
            try:
                draft = await draft_summary(body)
            finally:
                active_inference -= 1
        else:
            draft = await draft_summary(body)
        workflow_id = str(uuid4())
        workflow = DischargeWorkflow(
            draft, on_change=lambda state: store.save(workflow_id, state)
        )
        workflows[workflow_id] = workflow
        return WorkflowResponse(workflow_id=workflow_id, snapshot=workflow.snapshot())

    @app.get("/workflows/{workflow_id}", response_model=WorkflowResponse)
    async def read_workflow(workflow_id: str) -> WorkflowResponse:
        return WorkflowResponse(
            workflow_id=workflow_id, snapshot=get_workflow(workflow_id).snapshot()
        )

    @app.post("/workflows/{workflow_id}/approve", response_model=WorkflowResponse)
    async def approve(workflow_id: str, body: RevisionRequest) -> WorkflowResponse:
        state = get_workflow(workflow_id).approve(body.expected_revision)
        return WorkflowResponse(workflow_id=workflow_id, snapshot=state)

    @app.patch("/workflows/{workflow_id}/note", response_model=WorkflowResponse)
    async def revise_note(workflow_id: str, body: NoteRevisionRequest) -> WorkflowResponse:
        state = get_workflow(workflow_id).revise_note(body.doctor_note, body.expected_revision)
        return WorkflowResponse(workflow_id=workflow_id, snapshot=state)

    @app.post("/workflows/{workflow_id}/checks", response_model=WorkflowResponse)
    async def run_checks(workflow_id: str, body: RevisionRequest) -> WorkflowResponse:
        state = await get_workflow(workflow_id).run_checks(body.expected_revision)
        return WorkflowResponse(workflow_id=workflow_id, snapshot=state)

    return app


app = create_app()
