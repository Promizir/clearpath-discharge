# ClearPath learning notes — historical implementation lessons

These notes preserve the original step-by-step learning sequence. For current
setup and features, use the repository's main README.

## Lesson 1: patient data and schemas

This lesson implements only synthetic patient identity and allergies. Encounter
details, billing, AI calls, and workflow approvals come in later lessons.
The JSON is a custom learning fixture, not a conformant FHIR resource.

- `mock_ehr.json` holds example data.
- `schemas.py` describes its required structure and loads it using Pydantic.
- `pyproject.toml` describes the project and declares its dependency.
- `.gitignore` excludes local environments, generated files, and secrets from Git.

From PowerShell, prepare an isolated environment once:

```powershell
Set-Location 'C:\Users\alokk\OneDrive\Desktop\Discharge_app_amd'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

Then run the lesson:

```powershell
.\.venv\Scripts\python.exe schemas.py
```

Expected output:

```text
Validated synthetic patient: PT-402 - John Doe
Recorded allergies: 1
Structure validation only; no clinical checks have run.
```

`-e .` installs this local project in editable mode, so Python source edits are
available without reinstalling it. This lesson runs from the source checkout;
shipping the fixture inside a distributable package is outside this lesson.
The dependency range is not an exact environment lock.

Try changing the patient's age to -1, run again, and read the validation error.
Restore 34 afterwards. You can also try removing `allergies`: it must be supplied
explicitly. Passing validation checks data structure, not clinical correctness.

## Lesson 2: expose a patient lookup through MCP

`mcp_server.py` registers `get_patient_ehr(patient_id)` as a tool. It reuses the
existing loader, checks that the requested ID matches the fixture, and returns
the validated record. An unknown ID raises a tool error. The tool never writes
to the fixture.

`demo_mcp.py` is a small learning client. It discovers the tool and calls it over
an in-memory MCP connection. This exercises MCP without an AI model or network
server. The tool reads the same synthetic fixture as lesson 1.

Install the updated dependencies and run from the project folder:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe demo_mcp.py
```

Expected application output (the library may also log messages):

```text
Available tools: get_patient_ehr
Received: PT-402 - John Doe
Recorded allergies: 1
```

Try an ID that is not in the fixture:

```powershell
.\.venv\Scripts\python.exe demo_mcp.py PT-999
```

This intentionally raises a tool error instead of returning PT-402's record.

Data flow: client -> MCP tool -> schema loader -> JSON fixture -> validated
record -> structured MCP response -> client.

FastMCP supplies tool discovery, input schemas, and protocol handling. An ordinary
function call would be simpler for Python-only code; MCP adds interoperability
with other MCP clients. This lesson stays on FastMCP 2.x to keep a consistent API.

`@mcp.tool()` registers the function. Its parameter type describes the input,
its return type describes the output, and its docstring describes its purpose.
`async with` opens and closes the client connection; `await` waits for an MCP
operation; `asyncio.run` starts the asynchronous example from a normal script.

Running `mcp_server.py` directly starts a stdio server waiting for MCP messages.
It does not open a webpage. You do not need to start it separately for the demo.

## Lesson 3: a structured pharmacy finding

The demo now also calls `check_pharmacy_safety` with a proposed medicine.
`ProposedMedication` validates each input item. `PharmacyFlag` describes one
finding, and `PharmacyCheckResult` describes the response.

The tool reuses `_get_patient_record`, a plain Python helper shared with the
lookup tool. It checks only the supplied synthetic scenario: the normalized
medicine name `amoxicillin` paired with the allergy name `penicillin`.
It does not understand brand names, combinations, dosage, interactions, or
other allergy relationships. `NO_DEMO_RULE_MATCH` is not clinical clearance;
both result statuses require review. No medicines or patient data are changed.

Run the same demo command. After the patient lookup, it now prints a `FLAGGED`
finding and `Clinician review required: True`.

Tests use Python's built-in `unittest`, so no test dependency is needed:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The tests exercise MCP calls for the planted conflict, normalized spelling,
an unrecognized medicine, an unknown patient, malformed inputs, and an unchanged
fixture. The medication list must contain at least one item.

## Lesson 4: a mock summary worker

`Encounter` adds diagnosis and procedure fields to the synthetic record.
`DraftRequest` describes clinician input; `DischargeSummaryDraft` describes the
unapproved output. `agents.py` contains `draft_summary`, an async function that
calls our EHR tool through MCP and assembles those sources into a draft.

This worker copies structured source fields and preserves the doctor note
verbatim. It does not call an AI model, extract medicines from text, resolve
conflicting sources, or produce a complete clinical discharge document.
Medicines are supplied explicitly as a separate list. The result is labelled
`MOCK` and `AWAITING_DOCTOR_REVIEW`; no approval or release action is implemented.

Run from the project folder:

```powershell
.\.venv\Scripts\python.exe demo_summary.py
```

The example prints the draft as formatted JSON. It stops before approval and
pharmacy checks. `demo_mcp.py` remains an independent example of calling tools.

`model_copy(deep=True)` makes independent copies of nested models so changing
the original request afterwards does not also change the returned draft.
`model_dump_json(indent=2)` converts the output model into readable JSON text.

Run all lesson tests with the existing unittest discovery command. Summary tests
check source preservation, draft status, unknown patients, blank notes, and
independence from later edits to the input.

## Lesson 5: simulated approval and draft revisions

`workflow.py` adds `DischargeWorkflow`, a class that holds one draft in memory.
Unlike the schema classes, it implements actions and transition rules:

- `snapshot()` returns an independent copy of the current revision and draft.
- `approve(expected_revision)` approves only the current revision.
- `revise_note(doctor_note, expected_revision)` validates an edit, increments the
  revision, and resets the draft to `AWAITING_DOCTOR_REVIEW`.
- `get_approved_draft()` rejects access until the current draft is approved.

`_check_revision` is a shared helper used by approval and editing. A stale revision
means the caller acted on an older draft. Invalid edits leave state unchanged.

```powershell
.\.venv\Scripts\python.exe demo_workflow.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The demo explicitly simulates doctor actions in code. There is no authentication,
database persistence, web endpoint, or concurrency control yet. State disappears
when the process exits. Approval here concerns the draft only; it does not mean
pharmacy clearance or final discharge. Existing tool demos remain independent
and do not enforce this gate until we connect them to the workflow in a later lesson.

`DischargeSummaryDraft.status` now allows `DOCTOR_APPROVED` as well as the initial
review state. The summary worker still creates unapproved drafts. A new workflow
also resets any supplied approval instead of trusting it.

## Lesson 6: connect approval to the pharmacy worker

`agents.check_pharmacy` calls the existing MCP pharmacy tool using medicines from
the supplied draft. `DischargeWorkflow.run_pharmacy(expected_revision)` checks
approval before calling that worker. It checks the revision again after `await`
because another task may have edited the draft in the meantime.

`WorkflowSnapshot.pharmacy_result` holds the finding for the current revision,
or `None` when no result is stored. Editing creates a new snapshot and clears old
findings. A failed rerun also leaves no stored result. Failures propagate as
exceptions; distinct pending/running/error display states are a later lesson.

The workflow rejects duplicate in-flight pharmacy checks and mismatched-patient
results. The running flag applies to one workflow object on one event loop; it
is not a database lock or a cross-process concurrency solution.

Run `demo_workflow.py` again to see a blocked check before approval, a saved
`FLAGGED` finding after approval, and invalidation after an edit. This is a
completed check, not pharmacy clearance or discharge authorization. The demo
rule still requires clinician review. An empty medicine list remains a tool
error; we have not defined a no-medication clearance policy.

The direct MCP demo remains a tool-level exercise that bypasses workflow rules.
Future application routes must use the workflow rather than invoke the worker
directly. Tests cover both real MCP calls and a deliberately paused worker to
verify that edits during an asynchronous operation cannot attach stale findings.

## Lesson 7: compare consumable quantities

Revision 2 in the workflow demo is an optional edit scenario, not a mandatory
second review. An unchanged approved revision can proceed without a new revision.

The fixture now contains structured `used_consumables` and `billed_consumables`.
These are hand-authored synthetic inputs, not extracted from an image or note.
`ConsumableQuantity` validates each line and `BillingData` groups the two lists.
Both lists are required; an explicitly empty list means no entries in that source.

`reconcile_consumables_bill` loads the patient, sums repeated entries by exact
item ID, and compares totals from both sources. Positive differences mean fewer
billed than recorded as used; negative differences mean more billed than used.
An item absent from a list contributes zero to this comparison. The check assumes
the supplied lists are the intended inputs; it does not prove source completeness.

`agents.check_billing` calls the tool through MCP. Run the standalone exercise:

```powershell
.\.venv\Scripts\python.exe demo_billing.py
```

Expected output:

```text
Billing check: DISCREPANCIES_FOUND
HEMOSTATIC_GAUZE: used=3, billed=1, difference=+2
SKIN_STAPLER: used=1, billed=0, difference=+1
Comparison only: the bill has not been changed.
```

There is no price catalog, revenue calculation, billing modification, or insurer
approval in this lesson. Matching quantities only means these two supplied lists
agree. Both outcomes still require review. Billing is not yet connected to the
approval workflow; the next lesson can coordinate it with pharmacy.

## Lesson 8: concurrent pharmacy and billing checks

`DischargeWorkflow.run_checks(expected_revision)` checks approval and starts both
workers with `asyncio.gather(..., return_exceptions=True)`. It waits for both,
checks that the revision is still current, and records each valid result or
worker error. A failed worker does not discard its sibling's successful finding.

Snapshots now include `billing_result`, `parallel_status`, and `check_errors`.
`COMPLETED` means both workers returned valid results, even if those results
contain findings. `FAILED` means at least one worker failed. Neither authorizes
discharge. Cancellation records `CANCELLED`; editing resets the new revision
to `NOT_STARTED` and invalidates all previous findings.

```powershell
.\.venv\Scripts\python.exe demo_parallel.py
```

This example approves revision 1 once and runs both checks, without any edit:

```text
Revision 1: parallel checks COMPLETED
Pharmacy: FLAGGED
Billing: DISCREPANCIES_FOUND
Completed checks report findings; they do not authorize discharge.
```

Both workers are scheduled concurrently; this is not a guarantee of simultaneous
CPU execution or a measured speed improvement for the tiny local fixture.
Tests use events to prove both workers start before either finishes, rather than
relying on elapsed-time thresholds.

The previous `run_pharmacy` lesson remains available. It shares the duplicate-run
guard and clears parallel-batch metadata when starting a standalone check.
Retrying `run_checks` currently reruns both workers. Results are stored after the
batch finishes; per-worker live events and timeouts are not implemented yet.

## Lesson 9: call the workflow over HTTP

`main.py` creates a FastAPI app. Routes translate JSON requests into calls to the
existing workflow, then serialize its snapshot as JSON. FastAPI reuses our
Pydantic schemas for input validation and API documentation. Uvicorn is the
server process that listens for HTTP requests and runs the app.

Install updated dependencies and start from the project folder:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/docs and use **Try it out** on these routes:

1. `POST /workflows` with:

```json
{
  "patient_id": "PT-402",
  "doctor_note": "Please prepare a discharge draft for review.",
  "proposed_medications": [{"name": "Amoxicillin"}]
}
```

2. Copy `workflow_id` from the response.
3. `POST /workflows/{workflow_id}/approve` with `{"expected_revision": 1}`.
4. `POST /workflows/{workflow_id}/checks` with `{"expected_revision": 1}`.
5. `GET /workflows/{workflow_id}` to retrieve the stored snapshot.

Optional: `PATCH /workflows/{workflow_id}/note` with
`{"expected_revision": 1, "doctor_note": "Updated note for review."}`. This
creates revision 2 and resets approval and findings.

Responses use 201 for creation, 200 for returned snapshots, 404 for unknown
workflow IDs, 409 for workflow conflicts, and 422 for invalid request bodies.
Draft creation uses 502 for a failed MCP lookup, including an unknown patient;
the tool protocol does not yet distinguish patient-not-found from other failures.
The checks route can return HTTP 200 with `parallel_status: FAILED`: callers must
inspect the workflow outcome, not just whether the HTTP request succeeded.

`create_app` creates an independent workflow dictionary for each app. IDs identify
individual workflows, so two workflows for the same patient remain separate.
Use one server process. Lesson 11 below adds persistence across restarts.
Approval is still simulated, without user authentication. This is a local
synthetic-data exercise. `/checks` waits for the batch; streaming is a later step.

Tests use FastAPI's in-process TestClient, which exercises routing and validation
without opening a network port. No new test framework is needed.

## Lesson 10: persistent snapshots with SQLite

`storage.py` introduces `SnapshotStore`, using Python's built-in `sqlite3` module.
It creates a database table with a unique `workflow_id` and the snapshot as JSON
text. `save` inserts a new row or updates the row for that ID, then commits the
transaction. `load` reads the JSON and validates it as `WorkflowSnapshot`.
Connections are closed after each operation with `contextlib.closing`.

Run this to create and save a complete demo snapshot:

```powershell
.\.venv\Scripts\python.exe demo_storage.py
```

The command prints a workflow ID and a second command. Run that command after
the first process has exited to load the snapshot from
`runtime/lesson_snapshots.db`. This demonstrates persistence across processes.
No ID means create-and-save; supplying an ID means load-only. Loading does not
run the workers or create a live `DischargeWorkflow` object.

The runtime directory is already excluded from Git. The source fixture remains
unchanged. No additional dependency installation is needed for this lesson.

SQL placeholders (`?`) keep values separate from SQL instructions. A primary key
makes workflow IDs unique. `ON CONFLICT ... DO UPDATE` updates the latest snapshot
for an existing ID; it does not retain previous revisions or provide an audit log.

In lesson 10 this module was standalone; lesson 11 below connects it to `main.py`.
The store
does not enforce workflow transitions or protect against stale application writes;
callers must coordinate those rules. Database schema migrations and multiple API
processes are outside this initial storage exercise.

## Lesson 11: persistent API workflows and restart recovery

The API now uses `runtime/discharge.db`, separate from the standalone storage
demo's `lesson_snapshots.db`. Workflows created before this integration existed
only in memory and cannot be recovered retroactively.

`create_app(database_path)` creates a store and a cache of live workflow objects.
If an ID is absent from the cache, the API loads its snapshot from SQLite and
calls `DischargeWorkflow.from_snapshot`. This preserves the stored revision,
approval, and findings. Unknown IDs still return 404.

Each workflow gets an `on_change` callback, a function to call whenever state
changes. `_commit_state` calls it before publishing new in-memory state. The API
supplies a callback that saves the snapshot under its workflow ID. Standalone
workflow demos still work without a callback.

Draft creation, approval, editing, the start of parallel checks, final results,
and cancellation now save snapshots. If checks were stored as `RUNNING` when
the server stopped, restoring that workflow marks them `FAILED` with an
interruption message and clears results. The stored approval remains, so checks
can be retried for that revision. Recovery occurs when the workflow is loaded.

SQLite request failures return HTTP 503. A failed save does not publish the
proposed state in memory. If saving final results fails after workers complete,
the last saved state may still be `RUNNING`; retry the checks, or restore after
restart to mark that batch interrupted. A committed database write whose HTTP
response is lost may already have applied; read the current snapshot before
retrying an edit.

Try a restart:

1. Start Uvicorn with the lesson 9 command and create a workflow in `/docs`.
2. Copy its ID, approve it, and run its checks.
3. Stop the server with Ctrl+C and start it again with the same command.
4. Use `GET /workflows/{workflow_id}` with the original ID. The snapshot remains.

Tests use temporary database paths and fresh app instances to exercise recovery,
check persistence before workers start, and verify failed saves do not silently
approve drafts. No new dependencies are required.

This version supports one API process. The in-memory cache and running guards
are not coordinated across multiple servers. SQLite operations are synchronous
and small; moving database work off the event loop is a later scaling concern.
The database stores latest snapshots, not an audit history. Approval remains
simulated and the app continues to use synthetic patient data.
