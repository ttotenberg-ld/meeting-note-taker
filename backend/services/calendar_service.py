from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


class CalendarService:
    def __init__(self, creds: Credentials):
        self.service = build("calendar", "v3", credentials=creds)

    def _parse_event(self, event: dict) -> dict:
        """Parse a Google Calendar event into our meeting format."""
        attendees = []
        for a in event.get("attendees", []):
            attendees.append(
                {
                    "name": a.get("displayName", a.get("email", "Unknown")),
                    "email": a.get("email", ""),
                    "organizer": a.get("organizer", False),
                }
            )

        return {
            "id": event.get("id", ""),
            "title": event.get("summary", "Untitled Meeting"),
            "start": event["start"].get("dateTime", event["start"].get("date")),
            "end": event["end"].get("dateTime", event["end"].get("date")),
            "attendees": attendees,
            "description": event.get("description", ""),
            "meeting_link": event.get("hangoutLink", ""),
        }

    def get_upcoming_meetings(self, max_results: int = 10) -> list[dict]:
        """Get upcoming meetings from the calendar."""
        now = datetime.now(timezone.utc).isoformat()

        events_result = (
            self.service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])
        return [self._parse_event(e) for e in events]

    def get_current_meeting(self) -> dict | None:
        """Get the best auto-detected meeting (must have 2+ attendees)."""
        meetings = self.get_upcoming_meetings()
        for meeting in meetings:
            if len(meeting["attendees"]) >= 2:
                return meeting
        return None
