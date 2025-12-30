"""Audio recording module using sounddevice."""

import tempfile
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.io import wavfile

SAMPLE_RATE = 16000  # Whisper expects 16kHz


class StreamingRecorder:
    """Event-driven audio recorder using sounddevice InputStream.

    Supports start/stop recording for hold-to-record functionality.
    """

    def __init__(self) -> None:
        self._buffer: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._is_recording: bool = False
        self._lock = threading.Lock()

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time: object,
        status: sd.CallbackFlags,
    ) -> None:
        """Called by sounddevice for each audio chunk.

        Note:
            frames, time, status are required by sounddevice's callback
            signature but not used in this implementation.
            - frames: same as len(indata), redundant
            - time: timestamp info, not needed for simple recording
            - status: error flags (e.g. overflow), currently ignored
        """
        if self._is_recording:
            with self._lock:
                self._buffer.append(indata.copy())

    def start(self) -> None:
        """Start recording audio."""
        with self._lock:
            self._buffer.clear()
            self._is_recording = True

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype=np.int16,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        """Stop recording and return audio data.

        Returns:
            Audio data as numpy array (int16).
        """
        self._is_recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        with self._lock:
            if not self._buffer:
                return np.array([], dtype=np.int16)
            return np.concatenate(self._buffer, axis=0)

    @property
    def is_recording(self) -> bool:
        """Return whether recording is in progress."""
        return self._is_recording


def save_audio(audio: np.ndarray) -> Path:
    """Save audio data to a temporary WAV file.

    Args:
        audio: Audio data as numpy array.

    Returns:
        Path to the saved WAV file.
    """
    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wavfile.write(temp_file.name, SAMPLE_RATE, audio)
    return Path(temp_file.name)


# Legacy functions for CLI compatibility


def record_audio(duration: float) -> np.ndarray:
    """Record audio from the microphone (blocking).

    Args:
        duration: Recording duration in seconds.

    Returns:
        Audio data as numpy array.
    """
    print(f"Recording for {duration} seconds...")
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype=np.int16,
    )
    sd.wait()
    print("Recording finished.")
    return audio


def record_and_save(duration: float) -> Path:
    """Record audio and save to a temporary file (blocking).

    Args:
        duration: Recording duration in seconds.

    Returns:
        Path to the saved WAV file.
    """
    audio = record_audio(duration)
    return save_audio(audio)
