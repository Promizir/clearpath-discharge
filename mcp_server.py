"""Read-only MCP tools for the synthetic patient and a demonstration check."""

from pathlib import Path
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from schemas import (
    BillingCheckResult,
    BillingDiscrepancy,
    ConsumableQuantity,
    PatientRecord,
    PharmacyCheckResult,
    PharmacyFlag,
    ProposedMedication,
    load_patient_record,
)


mcp = FastMCP("Hospital-Discharge-MCP")
EHR_PATH = Path(__file__).resolve().with_name("mock_ehr.json")


def _get_patient_record(patient_id: str) -> PatientRecord:
    """Shared Python helper; it is not registered as an MCP tool."""
    record = load_patient_record(EHR_PATH)
    if record.patient_id != patient_id:
        raise ToolError(f"Patient {patient_id} not found")
    return record


@mcp.tool()
def get_patient_ehr(patient_id: str) -> PatientRecord:
    """Fetch the validated synthetic patient record for the requested patient ID."""
    return _get_patient_record(patient_id)


@mcp.tool()
def check_pharmacy_safety(
    patient_id: str,
    prescribed_meds: Annotated[list[ProposedMedication], Field(min_length=1)],
) -> PharmacyCheckResult:
    """Check the synthetic amoxicillin/penicillin scenario; never grant clearance."""
    record = _get_patient_record(patient_id)
    flags = []

    for medication in prescribed_meds:
        for allergy in record.patient.allergies:
            # Exact normalized names for our fixture, not a clinical drug database.
            if (
                medication.name.strip().casefold() == "amoxicillin"
                and allergy.substance.strip().casefold() == "penicillin"
            ):
                flags.append(
                    PharmacyFlag(
                        medication=medication.name,
                        matched_allergy=allergy.substance,
                        reason="Proposed medicine matches the demo allergy-conflict rule; clinician review required.",
                    )
                )

    return PharmacyCheckResult(
        patient_id=record.patient_id,
        status="FLAGGED" if flags else "NO_DEMO_RULE_MATCH",
        flags=flags,
    )


def _sum_quantities(items: list[ConsumableQuantity]) -> dict[str, int]:
    """Add quantities for each exact item ID, including repeated line items."""
    totals = {}
    for item in items:
        totals[item.item_id] = totals.get(item.item_id, 0) + item.quantity
    return totals


@mcp.tool()
def reconcile_consumables_bill(patient_id: str) -> BillingCheckResult:
    """Compare synthetic recorded usage with billed quantities without changing the bill."""
    record = _get_patient_record(patient_id)
    used = _sum_quantities(record.billing.used_consumables)
    billed = _sum_quantities(record.billing.billed_consumables)
    discrepancies = []

    # Include IDs from either source, so excess billing is also detected.
    for item_id in sorted(used.keys() | billed.keys()):
        used_quantity = used.get(item_id, 0)
        billed_quantity = billed.get(item_id, 0)
        difference = used_quantity - billed_quantity
        if difference != 0:
            discrepancies.append(
                BillingDiscrepancy(
                    item_id=item_id,
                    used_quantity=used_quantity,
                    billed_quantity=billed_quantity,
                    quantity_difference=difference,
                )
            )

    return BillingCheckResult(
        patient_id=record.patient_id,
        status="DISCREPANCIES_FOUND" if discrepancies else "QUANTITIES_MATCH",
        discrepancies=discrepancies,
    )


if __name__ == "__main__":
    # Start a server that exchanges MCP messages through standard input/output.
    mcp.run()
