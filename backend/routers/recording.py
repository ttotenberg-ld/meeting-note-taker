import os
from datetime import datetime
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


class StartRequest(BaseModel):
    meeting: dict[str, Any] | None = None
    custom_title: str | None = None


@router.post("/start")
async def start_recording(request: StartRequest):
    global recorder, current_meeting, processing_status

    processing_status = {"state": "recording", "step": "", "error": None}

    if request.meeting:
        # User selected a specific calendar meeting
        current_meeting = request.meeting
    elif request.custom_title:
        # User entered a custom title (no calendar meeting)
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

    processing_status = {"state": "processing", "step": "Transcribing audio...", "error": None}

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


def process_recording(wav_path: str, meeting_info: dict, timestamp: str):
    """Background task: transcribe, format, save, upload."""
    global processing_status

    transcript_dir = os.getenv("TRANSCRIPT_DIR", "")
    notes_dir = os.getenv("NOTES_DIR", "")
    api_key = os.getenv("GEMINI_API_KEY", "")
    title = meeting_info.get("title", "untitled")

    try:
        # 1. Transcribe
        processing_status["step"] = "Transcribing audio..."
        transcriber = TranscriptionService(api_key)
        transcript_text = transcriber.transcribe(wav_path)

        # 2. Save transcript
        processing_status["step"] = "Saving transcript..."
        transcript_filename = transcriber.save_transcript(
            transcript_text, title, transcript_dir, timestamp
        )

        # 3. Format notes
        processing_status["step"] = "Generating structured notes..."
        formatter = NoteFormatter(api_key)
        notes_content = formatter.format_notes(
            transcript_text, meeting_info, transcript_filename
        )

        # 4. Save notes
        processing_status["step"] = "Saving notes..."
        notes_filename = formatter.save_notes(
            notes_content, title, notes_dir, timestamp
        )

        # 5. Upload to Google Drive
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

        # Clean up WAV
        if os.path.exists(wav_path):
            os.remove(wav_path)

        processing_status = {"state": "idle", "step": "Done!", "error": None}

    except Exception as e:
        processing_status = {
            "state": "idle",
            "step": "",
            "error": str(e),
        }
        print(f"Processing failed: {e}")
