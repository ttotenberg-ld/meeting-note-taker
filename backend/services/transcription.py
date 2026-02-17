import os
import time

from google import genai

# 10-minute timeout for large audio files (default is 60s which is
# too short for 1-hour+ recordings).
GEMINI_TIMEOUT = 600_000  # 10 minutes in milliseconds (SDK uses ms)


class TranscriptionService:
    def __init__(self, api_key: str):
        self.client = genai.Client(
            api_key=api_key,
            http_options={"timeout": GEMINI_TIMEOUT},
        )
        self.model = "gemini-2.5-flash"

    def _wait_for_file_active(self, uploaded_file, poll_interval: int = 2, max_wait: int = 300):
        """Poll until an uploaded file reaches ACTIVE state.

        Large files need server-side processing after upload before they
        can be used in generate_content().
        """
        start = time.time()
        while uploaded_file.state.name == "PROCESSING":
            if time.time() - start > max_wait:
                raise TimeoutError(
                    f"Uploaded file did not become active within {max_wait}s"
                )
            time.sleep(poll_interval)
            uploaded_file = self.client.files.get(name=uploaded_file.name)
        if uploaded_file.state.name != "ACTIVE":
            raise RuntimeError(
                f"File upload failed with state: {uploaded_file.state.name}"
            )
        return uploaded_file

    def transcribe(self, wav_path: str, on_status=None) -> str:
        """Upload WAV to Gemini Files API and get a transcript.

        Args:
            wav_path: Path to the WAV file.
            on_status: Optional callback(str) for progress updates.
        """
        if on_status:
            on_status("Uploading audio to Gemini...")
        uploaded_file = self.client.files.upload(file=wav_path)

        if on_status:
            on_status("Waiting for file processing...")
        uploaded_file = self._wait_for_file_active(uploaded_file)

        if on_status:
            on_status("Transcribing audio (this may take a few minutes)...")

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
