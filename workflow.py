"""Lesson 5: in-memory draft revisions and a simulated doctor approval gate."""

import asyncio
from collections.abc import Callable

from agents import check_billing, check_pharmacy
from schemas import BillingCheckResult, DischargeSummaryDraft, PharmacyCheckResult, WorkflowSnapshot


class WorkflowConflict(ValueError):
    """An action conflicts with the current revision or workflow state."""


class DischargeWorkflow:
    def __init__(
        self,
        draft: DischargeSummaryDraft,
        on_change: Callable[[WorkflowSnapshot], None] | None = None,
    ):
        # A new workflow always starts unapproved, regardless of input status.
        initial = DischargeSummaryDraft.model_validate(draft.model_dump())
        initial.status = "AWAITING_DOCTOR_REVIEW"
        self._state = WorkflowSnapshot(revision=1, draft=initial)
        self._checks_running = False
        self._on_change = on_change
        self._commit_state(self._state)

    def _commit_state(self, next_state: WorkflowSnapshot) -> None:
        """Save first; publish the new in-memory state only if saving succeeds."""
        if self._on_change is not None:
            self._on_change(next_state.model_copy(deep=True))
        self._state = next_state

    @classmethod
    def from_snapshot(
        cls,
        snapshot: WorkflowSnapshot,
        on_change: Callable[[WorkflowSnapshot], None] | None = None,
    ) -> "DischargeWorkflow":
        """Restore trusted storage, preserving approval and recovering interrupted work."""
        restored = WorkflowSnapshot.model_validate(snapshot.model_dump())
        workflow = cls(restored.draft)
        workflow._on_change = on_change
        if restored.parallel_status == "RUNNING":
            restored.parallel_status = "FAILED"
            restored.pharmacy_result = None
            restored.billing_result = None
            restored.check_errors = {
                "workflow": "Checks were interrupted by a restart. Run checks again."
            }
        workflow._commit_state(restored)
        return workflow

    def snapshot(self) -> WorkflowSnapshot:
        """Return a copy so callers cannot edit the internal state accidentally."""
        return self._state.model_copy(deep=True)

    def _check_revision(self, expected_revision: int) -> None:
        """Shared guard for actions based on the revision a reviewer saw."""
        if expected_revision != self._state.revision:
            raise WorkflowConflict(
                f"Stale revision {expected_revision}; current revision is "
                f"{self._state.revision}. Review the current draft first."
            )

    def approve(self, expected_revision: int) -> WorkflowSnapshot:
        """Simulate doctor approval of the exact current draft revision."""
        self._check_revision(expected_revision)
        updated = self.snapshot()
        updated.draft.status = "DOCTOR_APPROVED"
        self._commit_state(updated)
        return self.snapshot()

    def revise_note(self, doctor_note: str, expected_revision: int) -> WorkflowSnapshot:
        """Validate an edit, advance the revision, and invalidate prior approval."""
        self._check_revision(expected_revision)
        updated = self._state.draft.model_dump()
        updated["doctor_note"] = doctor_note
        updated["status"] = "AWAITING_DOCTOR_REVIEW"
        # Generated prose belongs to the old note and must never survive an edit.
        updated.update(
            clinical_summary=None, review_notes=[], generation_mode="MOCK",
            model_name=None, inference_ms=None,
        )
        # Validate before replacing state: an invalid edit must change nothing.
        validated = DischargeSummaryDraft.model_validate(updated)
        next_state = WorkflowSnapshot(
            revision=self._state.revision + 1, draft=validated
        )
        self._commit_state(next_state)
        return self.snapshot()

    def get_approved_draft(self) -> DischargeSummaryDraft:
        """Gate for future downstream workers; approval is not discharge clearance."""
        if self._state.draft.status != "DOCTOR_APPROVED":
            raise WorkflowConflict("Doctor approval is required before using this draft downstream.")
        return self._state.draft.model_copy(deep=True)

    async def run_pharmacy(self, expected_revision: int) -> WorkflowSnapshot:
        """Check an approved revision and store findings only if it stays current."""
        self._check_revision(expected_revision)
        approved_draft = self.get_approved_draft()
        if self._checks_running:
            raise WorkflowConflict("A check is already running for this workflow.")

        updated = self.snapshot()
        updated.pharmacy_result = None
        updated.billing_result = None
        updated.parallel_status = "NOT_STARTED"
        updated.check_errors = {}
        self._commit_state(updated)
        self._checks_running = True
        try:
            result = await check_pharmacy(approved_draft)
            # Another task may have edited the draft while we were awaiting MCP.
            self._check_revision(expected_revision)
            if result.patient_id != approved_draft.patient_id:
                raise ValueError("Pharmacy result belongs to a different patient.")
            updated = self.snapshot()
            updated.pharmacy_result = result.model_copy(deep=True)
            self._commit_state(updated)
            return self.snapshot()
        finally:
            # Reset even if the worker fails or its result is outdated.
            self._checks_running = False

    async def run_checks(self, expected_revision: int) -> WorkflowSnapshot:
        """Run independent workers concurrently and retain explicit partial failures."""
        self._check_revision(expected_revision)
        approved_draft = self.get_approved_draft()
        if self._checks_running:
            raise WorkflowConflict("A check is already running for this workflow.")

        updated = self.snapshot()
        updated.pharmacy_result = None
        updated.billing_result = None
        updated.check_errors = {}
        updated.parallel_status = "RUNNING"
        self._commit_state(updated)
        self._checks_running = True
        try:
            pharmacy, billing = await asyncio.gather(
                check_pharmacy(approved_draft),
                check_billing(approved_draft.patient_id),
                return_exceptions=True,
            )
            # Reject the whole batch if its approved revision is no longer current.
            self._check_revision(expected_revision)
            updated = self.snapshot()
            for name, outcome, expected_type in (
                ("pharmacy", pharmacy, PharmacyCheckResult),
                ("billing", billing, BillingCheckResult),
            ):
                if isinstance(outcome, BaseException):
                    updated.check_errors[name] = str(outcome) or type(outcome).__name__
                elif not isinstance(outcome, expected_type):
                    updated.check_errors[name] = "Worker returned an unexpected result type."
                elif outcome.patient_id != approved_draft.patient_id:
                    updated.check_errors[name] = "Worker result belongs to a different patient."
                elif name == "pharmacy":
                    updated.pharmacy_result = outcome.model_copy(deep=True)
                else:
                    updated.billing_result = outcome.model_copy(deep=True)

            updated.parallel_status = "FAILED" if updated.check_errors else "COMPLETED"
            self._commit_state(updated)
            return self.snapshot()
        except asyncio.CancelledError:
            if self._state.revision == expected_revision:
                updated = self.snapshot()
                updated.parallel_status = "CANCELLED"
                self._commit_state(updated)
            raise
        finally:
            self._checks_running = False
