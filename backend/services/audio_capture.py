import os
import subprocess
import sys
import threading
import wave
from datetime import datetime
from pathlib import Path
from shutil import which

import numpy as np
import pyaudio

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100


def _find_audiotee_binary() -> str | None:
    """Locate the audiotee binary.

    Search order:
      1. backend/bin/audiotee  (dev mode — checked in or built locally)
      2. Bundled in the PyInstaller _MEIPASS directory
      3. On $PATH
    """
    # 1. Relative to this file: backend/bin/audiotee
    backend_dir = Path(__file__).resolve().parent.parent
    local_bin = backend_dir / "bin" / "audiotee"
    if local_bin.is_file() and os.access(local_bin, os.X_OK):
        return str(local_bin)

    # 2. PyInstaller bundle
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = Path(meipass) / "bin" / "audiotee"
        if bundled.is_file() and os.access(bundled, os.X_OK):
            return str(bundled)

    # 3. On PATH
    found = which("audiotee")
    if found:
        return found

    return None


class AudioRecorder:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.is_recording = False
        self.audio = pyaudio.PyAudio()
        self.mic_frames: list[bytes] = []
        self.system_frames: list[bytes] = []
        self.mic_thread: threading.Thread | None = None
        self.system_thread: threading.Thread | None = None
        self.audiotee_proc: subprocess.Popen | None = None
        self.output_path: str | None = None
        self.start_time: datetime | None = None
        self._audiotee_binary = _find_audiotee_binary()

    # ---- Mic recording (PyAudio) ----

    def _record_mic(self):
        """Record from the default microphone via PyAudio."""
        stream = self.audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=None,  # default mic
            frames_per_buffer=CHUNK,
        )
        while self.is_recording:
            data = stream.read(CHUNK, exception_on_overflow=False)
            self.mic_frames.append(data)
        stream.stop_stream()
        stream.close()

    # ---- System audio recording (AudioTee subprocess) ----

    def _record_system_audio(self):
        """Capture system audio via AudioTee subprocess.

        AudioTee streams raw PCM to stdout.  Using --sample-rate to
        match our mic rate (44100) also gives us 16-bit signed int LE
        output — the same format as PyAudio paInt16.
        """
        cmd = [
            self._audiotee_binary,
            "--sample-rate",
            str(RATE),  # 44100 → converts to 16-bit signed int LE mono
        ]
        self.audiotee_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,  # suppress AudioTee JSON logs
        )

        # Read fixed-size chunks that match our PyAudio config.
        # 16-bit mono → 2 bytes per sample → CHUNK * 2 bytes per read.
        bytes_per_read = CHUNK * 2

        while self.is_recording:
            data = self.audiotee_proc.stdout.read(bytes_per_read)
            if not data:
                break
            self.system_frames.append(data)

    # ---- Public API ----

    def get_available_devices(self) -> list[dict]:
        """List all available audio input devices."""
        devices = []
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                devices.append(
                    {
                        "index": i,
                        "name": info["name"],
                        "channels": info["maxInputChannels"],
                    }
                )
        return devices

    def start(self, meeting_title: str = "untitled"):
        """Start recording from mic + system audio."""
        os.makedirs(self.output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        safe_title = meeting_title.replace(" ", "_").replace("/", "-")
        self.output_path = os.path.join(
            self.output_dir, f"{timestamp}_{safe_title}.wav"
        )

        self.mic_frames = []
        self.system_frames = []
        self.is_recording = True
        self.start_time = datetime.now()

        # Mic thread (always runs)
        self.mic_thread = threading.Thread(
            target=self._record_mic,
            daemon=True,
        )

        # System audio thread (only if audiotee binary is available)
        if self._audiotee_binary:
            self.system_thread = threading.Thread(
                target=self._record_system_audio,
                daemon=True,
            )
        else:
            self.system_thread = None
            print(
                "[AudioRecorder] audiotee binary not found — "
                "recording mic only (no system audio)"
            )

        self.mic_thread.start()
        if self.system_thread:
            self.system_thread.start()

    def stop(self) -> str:
        """Stop recording and mix streams into a single WAV file."""
        self.is_recording = False

        # Stop AudioTee subprocess gracefully
        if self.audiotee_proc:
            self.audiotee_proc.terminate()
            try:
                self.audiotee_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.audiotee_proc.kill()
            self.audiotee_proc = None

        self.mic_thread.join(timeout=5)
        if self.system_thread:
            self.system_thread.join(timeout=5)

        # Convert captured bytes to numpy arrays
        mic_audio = np.frombuffer(b"".join(self.mic_frames), dtype=np.int16).astype(
            np.float32
        )

        if self.system_frames:
            sys_audio = np.frombuffer(
                b"".join(self.system_frames), dtype=np.int16
            ).astype(np.float32)

            # Pad the shorter array to match lengths
            max_len = max(len(mic_audio), len(sys_audio))
            mic_audio = np.pad(mic_audio, (0, max_len - len(mic_audio)))
            sys_audio = np.pad(sys_audio, (0, max_len - len(sys_audio)))

            mixed = ((mic_audio + sys_audio) / 2).clip(-32768, 32767).astype(np.int16)
        else:
            mixed = mic_audio.clip(-32768, 32767).astype(np.int16)

        with wave.open(self.output_path, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(mixed.tobytes())

        return self.output_path

    def get_elapsed_seconds(self) -> int:
        """Get seconds since recording started."""
        if self.start_time and self.is_recording:
            return int((datetime.now() - self.start_time).total_seconds())
        return 0

    def cleanup(self):
        """Release PyAudio resources."""
        self.audio.terminate()
