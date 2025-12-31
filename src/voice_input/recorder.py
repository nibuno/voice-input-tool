"""Audio recording module using sounddevice."""

import tempfile
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.io import wavfile

from .logger import get_logger

SAMPLE_RATE = 16000  # Whisper expects 16kHz

logger = get_logger()


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
        # Log audio stream status if there's an issue
        if status:
            logger.warning(f"Audio callback status: {status}")

        if self._is_recording:
            with self._lock:
                self._buffer.append(indata.copy())

    def start(self) -> None:
        """Start recording audio."""
        logger.info("Recording started")
        try:
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
            logger.debug("Audio stream opened successfully")
        except Exception as e:
            logger.exception(f"Failed to start recording: {e}")
            raise

    def stop(self) -> np.ndarray:
        """Stop recording and return audio data.

        Returns:
            Audio data as numpy array (int16).
        """
        logger.info("Recording stopped")
        try:
            self._is_recording = False
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None
                logger.debug("Audio stream closed successfully")

            with self._lock:
                buffer_count = len(self._buffer)
                if not self._buffer:
                    logger.debug("Recording buffer is empty")
                    return np.array([], dtype=np.int16)
                audio_data = np.concatenate(self._buffer, axis=0)
                duration_sec = len(audio_data) / SAMPLE_RATE
                logger.info(
                    f"Recording complete: {buffer_count} chunks, "
                    f"{len(audio_data)} samples, {duration_sec:.2f}s"
                )
                return audio_data
        except Exception as e:
            logger.exception(f"Failed to stop recording: {e}")
            raise

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
    try:
        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_path = Path(temp_file.name)
        temp_file.close()  # Close file handle before writing
        wavfile.write(str(temp_path), SAMPLE_RATE, audio)
        file_size = temp_path.stat().st_size
        logger.debug(f"Audio saved to {temp_path} ({file_size} bytes)")
        return temp_path
    except Exception as e:
        logger.exception(f"Failed to save audio: {e}")
        raise


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
