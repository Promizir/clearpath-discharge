"""Simulate review events; no real clinician authentication is implemented."""

import asyncio

from agents import draft_summary
from schemas import DraftRequest, ProposedMedication
from workflow import DischargeWorkflow


async def main() -> None:
    draft = await draft_summary(
        DraftRequest(
            patient_id="PT-402",
            doctor_note="Please prepare a draft for review.",
            proposed_medications=[ProposedMedication(name="Amoxicillin")],
        )
    )
    workflow = DischargeWorkflow(draft)
    print("Initial:", workflow.snapshot().draft.status)

    try:
        await workflow.run_pharmacy(expected_revision=1)
    except ValueError as error:
        print("Check before approval blocked:", error)

    approved = workflow.approve(expected_revision=1)
    print(f"Revision {approved.revision}:", approved.draft.status)

    checked = await workflow.run_pharmacy(expected_revision=1)
    print("Pharmacy result:", checked.pharmacy_result.status)

    revised = workflow.revise_note(
        "Updated clinician note for review.", expected_revision=1
    )
    print(f"Revision {revised.revision} after edit:", revised.draft.status)
    print("Previous pharmacy result cleared:", revised.pharmacy_result is None)

    try:
        workflow.approve(expected_revision=1)
    except ValueError as error:
        print("Old approval rejected:", error)

    try:
        workflow.get_approved_draft()
    except ValueError as error:
        print("Downstream access blocked:", error)

    approved = workflow.approve(expected_revision=2)
    print(f"Revision {approved.revision}:", approved.draft.status)

    checked = await workflow.run_pharmacy(expected_revision=2)
    print("Pharmacy result for new revision:", checked.pharmacy_result.status)
    print("A completed check is not discharge clearance; review is still required.")


if __name__ == "__main__":
    asyncio.run(main())
