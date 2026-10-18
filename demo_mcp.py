"""Call our MCP tool locally, without a model, API key, or separate server."""

import asyncio
import sys

from fastmcp import Client

from mcp_server import mcp
from schemas import PatientRecord, PharmacyCheckResult


async def main(patient_id: str) -> None:
    # Passing the server object connects the client in the same Python process.
    async with Client(mcp) as client:
        tools = await client.list_tools()
        print("Available tools:", ", ".join(tool.name for tool in tools))

        result = await client.call_tool("get_patient_ehr", {"patient_id": patient_id})
        # Convert the structured tool response back into our typed record.
        record = PatientRecord.model_validate(result.structured_content)
        print(f"Received: {record.patient_id} - {record.patient.name}")
        print(f"Recorded allergies: {len(record.patient.allergies)}")

        pharmacy_result = await client.call_tool(
            "check_pharmacy_safety",
            {
                "patient_id": patient_id,
                "prescribed_meds": [{"name": "Unknown medicine"}],
            },
        )
        check = PharmacyCheckResult.model_validate(
            pharmacy_result.structured_content)
        print(f"Demo pharmacy check: {check.status}")
        for flag in check.flags:
            print(f"- {flag.medication} / {flag.matched_allergy}: {flag.reason}")
        print(f"Clinician review required: {check.review_required}")


if __name__ == "__main__":
    requested_id = sys.argv[1] if len(sys.argv) > 1 else "PT-402"
    asyncio.run(main(requested_id))
