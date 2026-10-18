"""Lesson 1: describe and validate the structure of synthetic patient data."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RecordModel(BaseModel):
    # Catch misspelled fields and reject values of the wrong type.
    model_config = ConfigDict(extra="forbid", strict=True)


class Allergy(RecordModel):
    substance: str = Field(min_length=1)
    criticality: Literal["LOW", "HIGH", "UNABLE_TO_ASSESS"]
    reaction: str = Field(min_length=1)


class Patient(RecordModel):
    name: str = Field(min_length=1)
    age: int = Field(ge=0, le=130)
    bed: str = Field(min_length=1)
    # Required: an absent allergy list must not silently become an empty one.
    allergies: list[Allergy]


class Encounter(RecordModel):
    primary_diagnosis: str = Field(min_length=1)
    procedure_performed: str = Field(min_length=1)


class ConsumableQuantity(RecordModel):
    item_id: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    quantity: int = Field(gt=0)


class BillingData(RecordModel):
    used_consumables: list[ConsumableQuantity]
    billed_consumables: list[ConsumableQuantity]


class PatientRecord(RecordModel):
    synthetic: Literal[True]
    patient_id: str = Field(pattern=r"^PT-[0-9]+$")
    patient: Patient
    encounter: Encounter
    billing: BillingData


class ProposedMedication(RecordModel):
    # This lesson checks names only; dosage and frequency come later.
    name: str = Field(min_length=1, max_length=120, pattern=r"\S")


class DraftRequest(RecordModel):
    patient_id: str = Field(pattern=r"^PT-[0-9]+$")
    doctor_note: str = Field(min_length=1, max_length=10000, pattern=r"\S")
    proposed_medications: list[ProposedMedication] = Field(max_length=30)
    use_ai: bool = False


class DischargeSummaryDraft(RecordModel):
    patient_id: str
    patient_name: str
    encounter: Encounter
    doctor_note: str = Field(min_length=1, pattern=r"\S")
    proposed_medications: list[ProposedMedication]
    generation_mode: Literal["MOCK", "AMD"] = "MOCK"
    clinical_summary: str | None = None
    review_notes: list[str] = Field(default_factory=list)
    model_name: str | None = None
    inference_ms: int | None = Field(default=None, ge=0)
    status: Literal["AWAITING_DOCTOR_REVIEW", "DOCTOR_APPROVED"] = "AWAITING_DOCTOR_REVIEW"


class PharmacyFlag(RecordModel):
    medication: str
    matched_allergy: str
    reason: str


class PharmacyCheckResult(RecordModel):
    patient_id: str
    status: Literal["FLAGGED", "NO_DEMO_RULE_MATCH"]
    flags: list[PharmacyFlag]
    # No match in one demonstration rule cannot establish medication safety.
    review_required: Literal[True] = True
    scope: Literal["SYNTHETIC_SINGLE_RULE_DEMO"] = "SYNTHETIC_SINGLE_RULE_DEMO"


class BillingDiscrepancy(RecordModel):
    item_id: str
    used_quantity: int = Field(ge=0)
    billed_quantity: int = Field(ge=0)
    # Positive: fewer billed than used. Negative: more billed than used.
    quantity_difference: int


class BillingCheckResult(RecordModel):
    patient_id: str
    status: Literal["DISCREPANCIES_FOUND", "QUANTITIES_MATCH"]
    discrepancies: list[BillingDiscrepancy]
    review_required: Literal[True] = True
    scope: Literal["SYNTHETIC_QUANTITY_COMPARISON"] = "SYNTHETIC_QUANTITY_COMPARISON"


class WorkflowSnapshot(RecordModel):
    revision: int = Field(ge=1)
    draft: DischargeSummaryDraft
    pharmacy_result: PharmacyCheckResult | None = None
    billing_result: BillingCheckResult | None = None
    parallel_status: Literal["NOT_STARTED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"] = "NOT_STARTED"
    check_errors: dict[str, str] = Field(default_factory=dict)


class RevisionRequest(RecordModel):
    expected_revision: int = Field(ge=1)


class NoteRevisionRequest(RevisionRequest):
    doctor_note: str = Field(min_length=1, max_length=10000, pattern=r"\S")


class WorkflowResponse(RecordModel):
    workflow_id: str
    snapshot: WorkflowSnapshot


def load_patient_record(path: Path) -> PatientRecord:
    """Read a fixture and reject data that does not match our schema."""
    return PatientRecord.model_validate_json(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    # Resolve the fixture beside this file, regardless of the terminal directory.
    fixture = Path(__file__).resolve().with_name("mock_ehr.json")
    record = load_patient_record(fixture)
    print(f"Validated synthetic patient: {record.patient_id} - {record.patient.name}")
    print(f"Recorded allergies: {len(record.patient.allergies)}")
    print("Structure validation only; no clinical checks have run.")
