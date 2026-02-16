import os
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()


@router.get("/list")
async def list_notes():
    notes_dir = os.getenv("NOTES_DIR", "")
    if not notes_dir or not os.path.exists(notes_dir):
        return {"notes": []}

    notes = []
    for f in sorted(Path(notes_dir).glob("*_notes.md"), reverse=True):
        # Parse filename: {timestamp}_{title}_notes.md
        parts = f.stem.rsplit("_notes", 1)[0]
        # Split on first underscore after timestamp (YYYY-MM-DD_HH-MM-SS)
        timestamp_end = 19  # len("YYYY-MM-DD_HH-MM-SS")
        if len(parts) > timestamp_end:
            timestamp = parts[:timestamp_end]
            title = parts[timestamp_end + 1 :].replace("_", " ")
        else:
            timestamp = parts
            title = "Untitled"

        notes.append(
            {
                "filename": f.name,
                "title": title,
                "date": timestamp.replace("_", " "),
            }
        )

    return {"notes": notes[:20]}  # Return last 20
