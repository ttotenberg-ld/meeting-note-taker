import os
import threading
import wave
from datetime import datetime

import numpy as np
import pyaudio

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100


class AudioRecorder:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.is_recording = False
        self.audio = pyaudio.PyAudio()
        self.mic_frames: list[bytes] = []
        self.system_frames: list[bytes] = []
        self.mic_thread: threading.Thread | None = None
        self.system_thread: threading.Thread | None = None
        self.output_path: str | None = None
        self.start_time: datetime | None = None

    def _find_device_index(self, name_substring: str) -> int | None:
        """Find a PyAudio device index by partial name match."""
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            if (
                name_substring.lower() in info["name"].lower()
                and info["maxInputChannels"] > 0
            ):
                return i
        return None

    def _record_stream(self, device_index: int | None, frames_list: list[bytes]):
        """Record from a specific device into the provided frames list."""
        stream = self.audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=CHUNK,
        )
        while self.is_recording:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames_list.append(data)
        stream.stop_stream()
        stream.close()

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
        """Start recording from both mic and BlackHole."""
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

        mic_index = None  # None = default mic
        blackhole_index = self._find_device_index("BlackHole")

        self.mic_thread = threading.Thread(
            target=self._record_stream,
            args=(mic_index, self.mic_frames),
            daemon=True,
        )

        if blackhole_index is not None:
            self.system_thread = threading.Thread(
                target=self._record_stream,
                args=(blackhole_index, self.system_frames),
                daemon=True,
            )
        else:
            self.system_thread = None

        self.mic_thread.start()
        if self.system_thread:
            self.system_thread.start()

    def stop(self) -> str:
        """Stop recording and mix streams into a single WAV file."""
        self.is_recording = False
        self.mic_thread.join(timeout=5)
        if self.system_thread:
            self.system_thread.join(timeout=5)

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
