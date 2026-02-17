import json
import os
import shutil
from pathlib import Path

from dotenv import dotenv_values
from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel

router = APIRouter()

ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
CREDENTIALS_PATH_DEFAULT = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "credentials.json"
)

# All user-configurable settings and their .env keys
SETTING_KEYS = [
    "GEMINI_API_KEY",
    "TRANSCRIPT_DIR",
    "NOTES_DIR",
    "DRIVE_FOLDER_NAME",
    "OBSIDIAN_VAULT_NAME",
    "OBSIDIAN_NOTES_SUBPATH",
]

# Keys that should never be exposed in full to the frontend
MASKED_KEYS = {"GEMINI_API_KEY"}


def _read_env() -> dict[str, str]:
    """Read current .env values."""
    if not os.path.exists(ENV_PATH):
        return {}
    return dotenv_values(ENV_PATH)


def _write_env(values: dict[str, str]):
    """Write values to .env, preserving keys not in `values`."""
    existing = _read_env()
    existing.update(values)

    # Always include these defaults
    existing.setdefault("GOOGLE_CREDENTIALS_PATH", "./credentials.json")
    existing.setdefault("GOOGLE_TOKEN_PATH", "./token.json")

    lines = []
    for key, val in existing.items():
        if val is not None:
            lines.append(f"{key}={val}")
    Path(ENV_PATH).write_text("\n".join(lines) + "\n")


def _mask(value: str) -> str:
    """Mask a secret value for display: show last 4 chars only."""
    if not value or len(value) <= 4:
        return "****"
    return "****" + value[-4:]


@router.get("")
async def get_settings():
    """Return current settings. Secrets are masked."""
    env = _read_env()
    settings = {}
    for key in SETTING_KEYS:
        val = env.get(key, "")
        if key in MASKED_KEYS and val:
            settings[key] = _mask(val)
        else:
            settings[key] = val or ""

    # Check if credentials.json exists
    creds_path = env.get("GOOGLE_CREDENTIALS_PATH", "./credentials.json")
    if not os.path.isabs(creds_path):
        creds_path = os.path.join(os.path.dirname(ENV_PATH), creds_path)
    settings["google_credentials_configured"] = os.path.exists(creds_path)

    # Check if token.json exists (user has completed OAuth)
    token_path = env.get("GOOGLE_TOKEN_PATH", "./token.json")
    if not os.path.isabs(token_path):
        token_path = os.path.join(os.path.dirname(ENV_PATH), token_path)
    settings["google_authenticated"] = os.path.exists(token_path)

    return settings


class SettingsUpdate(BaseModel):
    GEMINI_API_KEY: str | None = None
    TRANSCRIPT_DIR: str | None = None
    NOTES_DIR: str | None = None
    DRIVE_FOLDER_NAME: str | None = None
    OBSIDIAN_VAULT_NAME: str | None = None
    OBSIDIAN_NOTES_SUBPATH: str | None = None


@router.post("")
async def update_settings(update: SettingsUpdate):
    """Update settings in .env. Only non-None fields are written."""
    changes = {}
    for key in SETTING_KEYS:
        val = getattr(update, key, None)
        if val is not None:
            changes[key] = val
    if changes:
        _write_env(changes)
        # Reload env vars into the current process
        for key, val in changes.items():
            os.environ[key] = val
    return {"status": "ok"}


@router.post("/credentials")
async def upload_credentials(file: UploadFile = File(...)):
    """Upload a Google OAuth credentials.json file."""
    content = await file.read()

    # Validate it's valid JSON with expected structure
    try:
        data = json.loads(content)
        if "installed" not in data and "web" not in data:
            return {
                "status": "error",
                "message": "Invalid credentials file. Expected a Google OAuth client JSON with an 'installed' key.",
            }
    except json.JSONDecodeError:
        return {"status": "error", "message": "File is not valid JSON."}

    # Write to credentials.json
    env = _read_env()
    creds_path = env.get("GOOGLE_CREDENTIALS_PATH", "./credentials.json")
    if not os.path.isabs(creds_path):
        creds_path = os.path.join(os.path.dirname(ENV_PATH), creds_path)

    Path(creds_path).write_bytes(content)

    # Remove any existing token so user re-authenticates with new credentials
    token_path = env.get("GOOGLE_TOKEN_PATH", "./token.json")
    if not os.path.isabs(token_path):
        token_path = os.path.join(os.path.dirname(ENV_PATH), token_path)
    if os.path.exists(token_path):
        os.remove(token_path)

    return {"status": "ok"}


@router.get("/setup-status")
async def setup_status():
    """Check if the app has minimum required configuration to function."""
    env = _read_env()
    gemini_ok = bool(env.get("GEMINI_API_KEY"))
    creds_path = env.get("GOOGLE_CREDENTIALS_PATH", "./credentials.json")
    if not os.path.isabs(creds_path):
        creds_path = os.path.join(os.path.dirname(ENV_PATH), creds_path)
    google_ok = os.path.exists(creds_path)
    paths_ok = bool(env.get("TRANSCRIPT_DIR")) and bool(env.get("NOTES_DIR"))

    return {
        "ready": gemini_ok and google_ok and paths_ok,
        "gemini_configured": gemini_ok,
        "google_configured": google_ok,
        "paths_configured": paths_ok,
    }
