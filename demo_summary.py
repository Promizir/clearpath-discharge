"""Run the mock summary worker and stop at a draft awaiting doctor review."""

import asyncio

from agents import draft_summary
from schemas import DraftRequest, ProposedMedication


async def main() -> None:
    request = DraftRequest(
        patient_id="PT-402",
        doctor_note="Please prepare a discharge draft for review. Follow up in clinic in 7 days.",
        # Explicit sample input: this lesson does not extract medicines from text.
        proposed_medications=[ProposedMedication(name="Amoxicillin")],
    )
    draft = await draft_summary(request)
    print(draft.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
