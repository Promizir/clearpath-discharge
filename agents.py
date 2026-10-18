"""Lesson 4: assemble a mock draft from source data, without an AI model."""

from fastmcp import Client

from mcp_server import mcp
from providers import generate_summary
from schemas import BillingCheckResult, DischargeSummaryDraft, DraftRequest, PatientRecord, PharmacyCheckResult


async def draft_summary(request: DraftRequest) -> DischargeSummaryDraft:
    """Copy EHR facts and supplied clinician input into an unapproved draft."""
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_patient_ehr", {"patient_id": request.patient_id}
        )
        record = PatientRecord.model_validate(result.structured_content)

    draft = DischargeSummaryDraft(
        patient_id=record.patient_id,
        patient_name=record.patient.name,
        encounter=record.encounter.model_copy(deep=True),
        doctor_note=request.doctor_note,
        proposed_medications=[
            medication.model_copy(deep=True)
            for medication in request.proposed_medications
        ],
    )
    if request.use_ai:
        generated, model, elapsed = await generate_summary(record, request)
        draft.clinical_summary = generated.clinical_summary
        draft.review_notes = generated.review_notes
        draft.model_name = model
        draft.inference_ms = elapsed
        draft.generation_mode = "AMD"
    return draft


async def check_pharmacy(draft: DischargeSummaryDraft) -> PharmacyCheckResult:
    """Call the demo pharmacy tool; the workflow controls permission to start."""
    async with Client(mcp) as client:
        result = await client.call_tool(
            "check_pharmacy_safety",
            {
                "patient_id": draft.patient_id,
                "prescribed_meds": [
                    medication.model_dump() for medication in draft.proposed_medications
                ],
            },
        )
    return PharmacyCheckResult.model_validate(result.structured_content)


async def check_billing(patient_id: str) -> BillingCheckResult:
    """Fetch a quantity comparison through MCP; this worker does not approve charges."""
    async with Client(mcp) as client:
        result = await client.call_tool(
            "reconcile_consumables_bill", {"patient_id": patient_id}
        )
    return BillingCheckResult.model_validate(result.structured_content)
