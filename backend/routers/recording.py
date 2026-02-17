import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from services.audio_capture import AudioRecorder
from services.drive_service import DriveService
from services.google_auth import get_credentials
from services.note_formatter import NoteFormatter
from services.transcription import TranscriptionService

router = APIRouter()

# Module-level state
recorder: AudioRecorder | None = None
current_meeting: dict | None = None
processing_status = {"state": "idle", "step": "", "error": None}

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 5  # seconds; doubles each retry (5, 10, 20)

# Directory for saved recordings that failed processing
SAVED_RECORDINGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "saved-recordings"
)


class StartRequest(BaseModel):
    meeting: dict[str, Any] | None = None
    custom_title: str | None = None


@router.post("/start")
async def start_recording(request: StartRequest):
    global recorder, current_meeting, processing_status

    processing_status = {"state": "recording", "step": "", "error": None}

    if request.meeting:
        current_meeting = request.meeting
    elif request.custom_title:
        current_meeting = {
            "title": request.custom_title,
            "start": "",
            "end": "",
            "attendees": [],
            "description": "",
            "meeting_link": "",
        }
    else:
        current_meeting = {
            "title": "untitled",
            "start": "",
            "end": "",
            "attendees": [],
            "description": "",
            "meeting_link": "",
        }

    title = current_meeting["title"]

    recorder = AudioRecorder(output_dir="/tmp/meeting-recordings")
    recorder.start(meeting_title=title)

    return {"status": "recording", "meeting": current_meeting}


@router.post("/stop")
async def stop_recording(background_tasks: BackgroundTasks):
    global recorder, current_meeting, processing_status

    if not recorder or not recorder.is_recording:
        return {"status": "error", "message": "Not currently recording"}

    wav_path = recorder.stop()
    recorder.cleanup()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    processing_status = {
        "state": "processing",
        "step": "Uploading audio to Gemini...",
        "error": None,
    }

    background_tasks.add_task(
        process_recording, wav_path, current_meeting or {}, timestamp
    )

    return {"status": "processing", "message": "Recording stopped. Processing..."}


@router.get("/status")
async def get_status():
    global recorder, processing_status
    elapsed = 0
    if recorder and recorder.is_recording:
        elapsed = recorder.get_elapsed_seconds()
    return {
        **processing_status,
        "elapsed_seconds": elapsed,
    }


@router.get("/saved")
async def list_saved_recordings():
    """List recordings that were saved after failed processing."""
    if not os.path.isdir(SAVED_RECORDINGS_DIR):
        return {"recordings": []}

    recordings = []
    for meta_file in sorted(
        Path(SAVED_RECORDINGS_DIR).glob("*.json"), reverse=True
    ):
        try:
            meta = json.loads(meta_file.read_text())
            wav_name = meta.get("wav_filename", "")
            wav_path = os.path.join(SAVED_RECORDINGS_DIR, wav_name)
            if os.path.exists(wav_path):
                recordings.append(
                    {
                        "id": meta_file.stem,
                        "title": meta.get("title", "Unknown"),
                        "timestamp": meta.get("timestamp", ""),
                        "error": meta.get("last_error", ""),
                        "retries": meta.get("retry_count", 0),
                    }
                )
        except (json.JSONDecodeError, KeyError):
            continue

    return {"recordings": recordings}


@router.post("/retry/{recording_id}")
async def retry_saved_recording(
    recording_id: str, background_tasks: BackgroundTasks
):
    """Retry processing a saved recording."""
    global processing_status

    meta_path = os.path.join(SAVED_RECORDINGS_DIR, f"{recording_id}.json")
    if not os.path.exists(meta_path):
        return {"status": "error", "message": "Recording not found"}

    meta = json.loads(Path(meta_path).read_text())
    wav_path = os.path.join(SAVED_RECORDINGS_DIR, meta["wav_filename"])
    if not os.path.exists(wav_path):
        return {"status": "error", "message": "Audio file missing"}

    processing_status = {
        "state": "processing",
        "step": "Retrying transcription...",
        "error": None,
    }

    background_tasks.add_task(
        process_recording,
        wav_path,
        meta.get("meeting_info", {}),
        meta.get("timestamp", datetime.now().strftime("%Y-%m-%d_%H-%M-%S")),
        saved_meta_path=meta_path,
    )

    return {"status": "processing", "message": "Retrying..."}


# ---- Background processing ----


def _save_recording_for_later(
    wav_path: str,
    meeting_info: dict,
    timestamp: str,
    error_msg: str,
    retry_count: int,
):
    """Move WAV to saved-recordings/ with a metadata JSON sidecar."""
    os.makedirs(SAVED_RECORDINGS_DIR, exist_ok=True)

    title = meeting_info.get("title", "untitled")
    safe_title = title.replace(" ", "_").replace("/", "-")
    recording_id = f"{timestamp}_{safe_title}"
    wav_filename = f"{recording_id}.wav"
    dest_wav = os.path.join(SAVED_RECORDINGS_DIR, wav_filename)

    # Move WAV (or leave in place if already in saved-recordings)
    if os.path.abspath(wav_path) != os.path.abspath(dest_wav):
        shutil.move(wav_path, dest_wav)

    # Write metadata
    meta = {
        "wav_filename": wav_filename,
        "title": title,
        "timestamp": timestamp,
        "meeting_info": meeting_info,
        "last_error": error_msg,
        "retry_count": retry_count,
        "saved_at": datetime.now().isoformat(),
    }
    meta_path = os.path.join(SAVED_RECORDINGS_DIR, f"{recording_id}.json")
    Path(meta_path).write_text(json.dumps(meta, indent=2))

    print(f"[Recording] Saved for later retry: {dest_wav}")
    return meta_path


def _cleanup_saved_recording(saved_meta_path: str | None, wav_path: str):
    """Remove the saved recording files after successful processing."""
    if os.path.exists(wav_path):
        os.remove(wav_path)

    if saved_meta_path and os.path.exists(saved_meta_path):
        os.remove(saved_meta_path)


def process_recording(
    wav_path: str,
    meeting_info: dict,
    timestamp: str,
    saved_meta_path: str | None = None,
):
    """Background task: transcribe, format, save, upload — with retries."""
    global processing_status

    transcript_dir = os.getenv("TRANSCRIPT_DIR", "")
    notes_dir = os.getenv("NOTES_DIR", "")
    api_key = os.getenv("GEMINI_API_KEY", "")
    title = meeting_info.get("title", "untitled")

    try:
        if not api_key:
            raise ValueError(
                "Gemini API key not configured. Go to Settings to add it."
            )
        if not transcript_dir or not notes_dir:
            raise ValueError(
                "Transcript/Notes directories not configured. Go to Settings."
            )

        # 1. Transcribe (with retries)
        def update_step(msg: str):
            processing_status["step"] = msg

        transcriber = TranscriptionService(api_key)
        transcript_text = _transcribe_with_retries(
            transcriber, wav_path, update_step
        )

        # 2. Save transcript
        processing_status["step"] = "Saving transcript..."
        transcript_filename = transcriber.save_transcript(
            transcript_text, title, transcript_dir, timestamp
        )

        # 3. Format notes (with retries)
        processing_status["step"] = "Generating structured notes..."
        formatter = NoteFormatter(api_key)
        notes_content = _format_with_retries(
            formatter, transcript_text, meeting_info, transcript_filename
        )

        # 4. Save notes
        processing_status["step"] = "Saving notes..."
        notes_filename = formatter.save_notes(
            notes_content, title, notes_dir, timestamp
        )

        # 5. Upload to Google Drive (non-fatal)
        processing_status["step"] = "Uploading to Google Drive..."
        try:
            creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "./credentials.json")
            token_path = os.getenv("GOOGLE_TOKEN_PATH", "./token.json")
            creds = get_credentials(creds_path, token_path)
            drive_svc = DriveService(creds)
            notes_filepath = os.path.join(notes_dir, notes_filename)
            folder_name = os.getenv("DRIVE_FOLDER_NAME", "notes")
            drive_svc.upload_notes_as_doc(
                notes_filepath, f"{title} - {timestamp}", folder_name
            )
        except Exception as e:
            print(f"Drive upload failed (non-fatal): {e}")

        # 6. Success — clean up WAV and any saved metadata
        _cleanup_saved_recording(saved_meta_path, wav_path)

        processing_status = {"state": "idle", "step": "Done!", "error": None}

    except Exception as e:
        # All retries exhausted — save recording for later
        error_msg = str(e)
        _save_recording_for_later(
            wav_path, meeting_info, timestamp, error_msg, retry_count=MAX_RETRIES
        )

        processing_status = {
            "state": "idle",
            "step": "",
            "error": f"{error_msg} — audio saved for retry.",
        }
        print(f"Processing failed after retries: {e}")


def _transcribe_with_retries(transcriber, wav_path, update_step):
    """Attempt transcription up to MAX_RETRIES times with backoff."""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return transcriber.transcribe(wav_path, on_status=update_step)
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                update_step(
                    f"Transcription failed (attempt {attempt}/{MAX_RETRIES}). "
                    f"Retrying in {delay}s..."
                )
                print(
                    f"[Recording] Transcription attempt {attempt} failed: {e}. "
                    f"Retrying in {delay}s..."
                )
                time.sleep(delay)
    raise last_error


def _format_with_retries(formatter, transcript_text, meeting_info, transcript_filename):
    """Attempt note formatting up to MAX_RETRIES times with backoff."""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return formatter.format_notes(
                transcript_text, meeting_info, transcript_filename
            )
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                print(
                    f"[Recording] Formatting attempt {attempt} failed: {e}. "
                    f"Retrying in {delay}s..."
                )
                time.sleep(delay)
    raise last_error
