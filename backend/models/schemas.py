from pydantic import BaseModel


class Attendee(BaseModel):
    name: str
    email: str
    organizer: bool = False


class MeetingInfo(BaseModel):
    title: str
    start: str
    end: str
    attendees: list[Attendee] = []
    description: str = ""
    meeting_link: str = ""


class RecordingStatus(BaseModel):
    state: str  # "idle", "recording", "processing"
    step: str = ""
    meeting: MeetingInfo | None = None
    elapsed_seconds: int = 0
    error: str | None = None


class NoteEntry(BaseModel):
    filename: str
    title: str
    date: str
    drive_url: str = ""
