import os

from google import genai


class NoteFormatter:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.5-flash"

    def format_notes(
        self,
        transcript: str,
        meeting_info: dict,
        transcript_filename: str,
    ) -> str:
        """Use Gemini to generate structured meeting notes from a transcript."""
        attendees_str = ", ".join(
            [a["name"] for a in meeting_info.get("attendees", [])]
        )
        if not attendees_str:
            attendees_str = "Unknown"

        prompt = f"""You are a meeting note assistant. Given the following meeting \
transcript and metadata, create structured meeting notes in Markdown format.

**Meeting Title**: {meeting_info.get("title", "Untitled Meeting")}
**Date**: {meeting_info.get("start", "Unknown")}
**Attendees**: {attendees_str}
**Meeting Description**: {meeting_info.get("description", "N/A")}

Format the notes with these exact sections:

## {meeting_info.get("title", "Untitled Meeting")}

**Date**: (formatted date)
**Attendees**: (comma-separated list)

### Meeting Purpose
(1-2 sentences summarizing why this meeting was held)

### Key Discussion Points
(Bulleted list of main topics discussed, with sub-bullets for details)

### Challenges & Concerns
(Bulleted list of problems, blockers, or concerns raised)

### Goals & Decisions
(Bulleted list of decisions made or goals agreed upon)

### Next Steps
(Bulleted list of action items, with the responsible person if identifiable)

### Raw Transcript
[[{transcript_filename}]]

---

Here is the transcript:

{transcript}
"""
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        return response.text

    def save_notes(
        self,
        notes_content: str,
        meeting_title: str,
        notes_dir: str,
        timestamp: str,
    ) -> str:
        """Save structured notes as a markdown file. Return the filename."""
        safe_title = meeting_title.replace(" ", "_").replace("/", "-")
        filename = f"{timestamp}_{safe_title}_notes.md"
        filepath = os.path.join(notes_dir, filename)

        with open(filepath, "w") as f:
            f.write(notes_content)

        return filename
