"""Make one real synthetic AMD draft and save non-secret execution evidence."""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents import draft_summary
from config import public_inference_settings
from providers import InferenceError
from schemas import DraftRequest


async def main():
    if not public_inference_settings()["configured"]:
        print("NOT READY: complete the AMD settings in .env. No model request made.")
        return 2
    request = DraftRequest(
        patient_id="PT-402",
        doctor_note="Prepare John Doe's discharge draft after laparoscopic appendectomy. The clinician reports a clean surgical wound and requests follow-up in 7 days. Review proposed medication against documented allergies.",
        proposed_medications=[{"name": "Amoxicillin"}],
        use_ai=True,
    )
    try:
        draft = await draft_summary(request)
    except InferenceError as error:
        print(f"NOT VERIFIED: {error}")
        return 1
    evidence = {
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "One real configured-endpoint response using synthetic data; not a clinical evaluation or hardware attestation.",
        "draft": draft.model_dump(),
    }
    path = ROOT / "submission" / "amd-execution-evidence.json"
    path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"SUCCESS: {draft.model_name}; {draft.inference_ms} ms; status {draft.status}.")
    print("Non-secret synthetic output saved to submission/amd-execution-evidence.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
