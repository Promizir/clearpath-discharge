"""Run both checks on one approved revision, with no edit or second approval."""

import asyncio

from agents import draft_summary
from schemas import DraftRequest, ProposedMedication
from workflow import DischargeWorkflow


async def main() -> None:
    draft = await draft_summary(
        DraftRequest(
            patient_id="PT-402",
            doctor_note="Please prepare a discharge draft for review.",
            proposed_medications=[ProposedMedication(name="Amoxicillin")],
        )
    )
    workflow = DischargeWorkflow(draft)
    workflow.approve(expected_revision=1)  # Simulated doctor action.
    state = await workflow.run_checks(expected_revision=1)
    print(f"Revision {state.revision}: parallel checks {state.parallel_status}")
    if state.pharmacy_result is not None:
        print("Pharmacy:", state.pharmacy_result.status)
    if state.billing_result is not None:
        print("Billing:", state.billing_result.status)
    for worker, message in state.check_errors.items():
        print(f"{worker} failed: {message}")
    print("Completed checks report findings; they do not authorize discharge.")


if __name__ == "__main__":
    asyncio.run(main())
