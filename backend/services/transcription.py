import os

from google import genai


class TranscriptionService:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.5-flash"

    def transcribe(self, wav_path: str) -> str:
        """Upload WAV to Gemini Files API and get a transcript."""
        uploaded_file = self.client.files.upload(file=wav_path)

        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                (
                    "Transcribe this audio recording of a meeting. "
                    "Include speaker labels where you can distinguish different speakers "
                    "(e.g., Speaker 1, Speaker 2). "
                    "Include timestamps approximately every few minutes. "
                    "Output the transcript as plain text, preserving the natural flow "
                    "of conversation."
                ),
                uploaded_file,
            ],
        )

        return response.text

    def save_transcript(
        self,
        transcript: str,
        meeting_title: str,
        transcript_dir: str,
        timestamp: str,
    ) -> str:
        """Save transcript as a markdown file. Return the filename (no path)."""
        safe_title = meeting_title.replace(" ", "_").replace("/", "-")
        filename = f"{timestamp}_{safe_title}_transcript.md"
        filepath = os.path.join(transcript_dir, filename)

        content = f"# Transcript: {meeting_title}\n"
        content += f"**Date**: {timestamp}\n\n"
        content += "---\n\n"
        content += transcript

        with open(filepath, "w") as f:
            f.write(content)

        return filename
