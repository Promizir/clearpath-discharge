"""Server-side inference settings. Secrets are never returned to the browser."""

import os
from pathlib import Path

from dotenv import load_dotenv


ENV_PATH = Path(__file__).resolve().with_name(".env")


def inference_settings() -> dict[str, str]:
    load_dotenv(ENV_PATH, override=False)
    return {
        "provider": os.getenv("AI_PROVIDER", "MOCK").strip().upper(),
        "base_url": os.getenv("AMD_BASE_URL", "").strip().rstrip("/"),
        "model": os.getenv("AMD_MODEL", "").strip(),
        "api_key": os.getenv("AMD_API_KEY", "").strip(),
    }


def public_inference_settings() -> dict[str, object]:
    settings = inference_settings()
    return {
        "provider": settings["provider"],
        "model": settings["model"],
        "configured": settings["provider"] == "AMD" and all(
            settings[name] for name in ("base_url", "model", "api_key")
        ),
        "synthetic_data_only": True,
    }
