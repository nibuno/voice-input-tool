"""Audio recording module using sounddevice."""

import queue
import tempfile
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.io import wavfile

from .logger import get_logger

SAMPLE_RATE = 16000  # Whisper expects 16kHz
ABORT_TIMEOUT = 1.0  # Timeout for stream.abort() in seconds
CLOSE_TIMEOUT = 1.0  # Timeout for stream.close() in seconds

logger = get_logger()


class StreamingRecorder:
    """Event-driven audio recorder using sounddevice InputStream.

    Supports start/stop recording for hold-to-record functionality.
    Uses queue.Queue instead of Lock for thread-safe buffer access.
    """

    def __init__(self) -> None:
        self._queue: queue.Queue[np.ndarray] = queue.Queue()
        self._stream: sd.InputStream | None = None
        self.is_recording: bool = False

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

        if self.is_recording:
            self._queue.put_nowait(indata.copy())

    def initialize(self) -> None:
        """Initialize the audio stream (call once at app startup).

        The stream is created in stopped state. Call start() to begin recording.
        """
        if self._stream is not None:
            raise RuntimeError("Stream already initialized")

        logger.info("Initializing audio stream...")
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype=np.int16,
            callback=self._audio_callback,
        )
        # Stream is created but not started (microphone not active)
        logger.info("Audio stream initialized successfully")

    def start(self) -> None:
        """Start recording audio.

        Requires initialize() to be called first.
        Resumes the stream and begins capturing audio.
        """
        if not self.is_initialized:
            raise RuntimeError("Stream not initialized. Call initialize() first.")

        # Clear queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

        self.is_recording = True
        self._stream.start()  # Resume stream (activates microphone)
        logger.info("Recording started")

    def _abort_with_timeout(self) -> bool:
        """Abort stream with timeout to prevent hanging.

        Returns:
            True if abort completed normally, False if timed out.
        """
        if not self._stream:
            return True

        def do_abort() -> None:
            try:
                self._stream.abort()
            except Exception as e:
                logger.warning(f"Exception in abort: {e}")

        thread = threading.Thread(target=do_abort)
        thread.start()
        thread.join(timeout=ABORT_TIMEOUT)

        if thread.is_alive():
            logger.warning(
                f"stream.abort() timed out after {ABORT_TIMEOUT}s, forcing continue"
            )
            return False
        return True

    def cleanup(self) -> None:
        """Clean up audio stream resources (call at app shutdown)."""
        logger.info("Cleaning up audio stream...")
        self.is_recording = False

        if self._stream is None:
            return

        abort_success = self._abort_with_timeout()
        if abort_success:
            try:
                self._stream.close()
            except Exception as e:
                logger.warning(f"Exception in close: {e}")

        self._stream = None
        logger.info("Audio stream cleanup complete")

    @property
    def is_initialized(self) -> bool:
        """Check if the stream is initialized (may be stopped or running)."""
        return self._stream is not None

    def stop(self) -> np.ndarray:
        """Stop recording and return audio data.

        Pauses the stream (deactivates microphone) and returns captured audio.

        Returns:
            Audio data as numpy array (int16).
        """
        self.is_recording = False

        # Pause stream (deactivates microphone)
        if self._stream is not None:
            self._stream.stop()

        logger.info("Recording stopped")

        # Collect data from queue
        chunks: list[np.ndarray] = []
        while True:
            try:
                chunk = self._queue.get_nowait()
                chunks.append(chunk)
            except queue.Empty:
                break

        buffer_count = len(chunks)
        if not chunks:
            logger.debug("Recording buffer is empty")
            return np.array([], dtype=np.int16)

        audio_data = np.concatenate(chunks, axis=0)
        duration_sec = len(audio_data) / SAMPLE_RATE
        logger.info(
            f"Recording complete: {buffer_count} chunks, "
            f"{len(audio_data)} samples, {duration_sec:.2f}s"
        )
        return audio_data


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
