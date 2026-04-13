"""Audio recording module using sounddevice."""

import queue
import tempfile
import threading
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.io import wavfile

from .logger import get_logger

SAMPLE_RATE = 16000  # Whisper expects 16kHz
ABORT_TIMEOUT = 1.0  # Timeout for stream.abort() in seconds
CLOSE_TIMEOUT = 1.0  # Timeout for stream.close() in seconds
STOP_TIMEOUT = 1.0  # Timeout for stream.stop() in seconds
TERMINATE_TIMEOUT = 2.0  # Timeout for Pa_Terminate() in seconds

logger = get_logger()


class UnrecoverableAudioError(RuntimeError):
    """Raised when PortAudio enters an unrecoverable state.

    Typically this means Pa_Terminate() timed out, leaving the PortAudio
    internal mutex held. Subsequent stream operations would deadlock, so the
    only recovery is to restart the process.
    """


class StreamingRecorder:
    """Event-driven audio recorder using sounddevice InputStream.

    Supports start/stop recording for hold-to-record functionality.
    Uses queue.Queue instead of Lock for thread-safe buffer access.
    """

    def __init__(self) -> None:
        self._queue: queue.Queue[np.ndarray] = queue.Queue()
        self._stream: sd.InputStream | None = None
        self.is_recording: bool = False
        self._device: int | None = None
        # Monotonic timestamp of the last audio callback while recording.
        # Used by the app to detect a silently-stalled AUHAL callback thread.
        self._last_callback_time: float | None = None

    def set_device(self, device: int | None) -> None:
        """Set the input device index (None = OS default)."""
        self._device = device

    def _create_stream(self) -> sd.InputStream:
        """Create an InputStream with the current device setting."""
        return sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype=np.int16,
            callback=self._audio_callback,
            device=self._device,
        )

    def _create_stream_with_fallback(self) -> sd.InputStream:
        """Create an InputStream, falling back to OS default on failure."""
        try:
            return self._create_stream()
        except sd.PortAudioError:
            if self._device is None:
                raise
            logger.warning("Configured device failed; falling back to OS default")
            self._device = None
            return self._create_stream()

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        _time: object,
        status: sd.CallbackFlags,
    ) -> None:
        """Called by sounddevice for each audio chunk.

        Note:
            frames, _time, status are required by sounddevice's callback
            signature but not used in this implementation.
            - frames: same as len(indata), redundant
            - _time: timestamp info, not needed for simple recording
              (renamed from ``time`` so it doesn't shadow the ``time`` module)
            - status: error flags (e.g. overflow), currently ignored
        """
        # Log audio stream status if there's an issue
        if status:
            logger.warning(f"Audio callback status: {status}")

        if self.is_recording:
            self._last_callback_time = time.monotonic()
            self._queue.put_nowait(indata.copy())

    def initialize(self) -> None:
        """Initialize the audio stream (call once at app startup).

        The stream is created in stopped state. Call start() to begin recording.
        """
        if self._stream is not None:
            raise RuntimeError("Stream already initialized")

        logger.info("Initializing audio stream...")
        self._stream = self._create_stream_with_fallback()
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
        # Seed the heartbeat so the stall detector waits for a real silence
        # window from _now_, not from whenever the stream was last active.
        self._last_callback_time = time.monotonic()
        self._stream.start()  # Resume stream (activates microphone)
        logger.info("Recording started")

    def seconds_since_last_callback(self) -> float | None:
        """Seconds since the last audio callback fired, or None if unknown."""
        last = self._last_callback_time
        if last is None:
            return None
        return time.monotonic() - last

    def _abort_with_timeout(self) -> bool:
        """Abort stream with timeout to prevent hanging.

        Returns:
            True if abort completed normally, False if timed out.
        """
        if not self._stream:
            return True

        def do_abort() -> None:
            # abort() has ignore_errors=True by default, so no exception is raised.
            # See: https://python-sounddevice.readthedocs.io/en/latest/_modules/sounddevice.html
            self._stream.abort()

        thread = threading.Thread(target=do_abort, daemon=True)
        thread.start()
        thread.join(timeout=ABORT_TIMEOUT)

        if thread.is_alive():
            logger.warning(
                f"stream.abort() timed out after {ABORT_TIMEOUT}s, forcing continue"
            )
            return False
        return True

    def _stop_with_timeout(self) -> bool:
        """Stop stream with timeout to prevent hanging.

        Returns:
            True if stop completed normally, False if timed out.
        """
        if not self._stream:
            return True

        def do_stop() -> None:
            # stop() has ignore_errors=True by default, so no exception is raised.
            # See: https://python-sounddevice.readthedocs.io/en/latest/_modules/sounddevice.html
            self._stream.stop()

        thread = threading.Thread(target=do_stop, daemon=True)
        thread.start()
        thread.join(timeout=STOP_TIMEOUT)

        if thread.is_alive():
            logger.warning(
                f"stream.stop() timed out after {STOP_TIMEOUT}s, falling back to abort()"
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
            # close() has ignore_errors=True by default, so no exception is raised.
            # See: https://python-sounddevice.readthedocs.io/en/latest/_modules/sounddevice.html
            self._stream.close()

        self._stream = None
        logger.info("Audio stream cleanup complete")

    @property
    def is_initialized(self) -> bool:
        """Check if the stream is initialized (may be stopped or running)."""
        return self._stream is not None

    def reinitialize(self) -> None:
        """Reinitialize the audio stream (for recovery from device errors).

        This resets the PortAudio subsystem entirely and creates a new stream.
        Required when the stream becomes stale after USB device re-enumeration
        (e.g., sleep/wake cycle), because Pa_Terminate() is the only way to
        destroy stale AUHAL units bound to invalidated CoreAudio AudioObjectIDs.
        """
        logger.info("Reinitializing audio stream...")

        # Clean up existing stream before touching PortAudio internals.
        # If abort() times out, the AUHAL callback thread is hung (e.g., device
        # physically disconnected).  In that state close() would also hang because
        # Pa_CloseStream() internally waits for the callback thread to finish.
        # Skip close() and let Pa_Terminate() forcibly destroy the AUHAL instead.
        if self._stream is not None:
            abort_success = self._abort_with_timeout()
            if not abort_success:
                logger.warning(
                    "stream.abort() timed out; skipping stream.close() — "
                    "Pa_Terminate() will forcibly clean up hung AUHAL resources"
                )
                self._stream = None  # Abandon the hung stream; Pa_Terminate() cleans up
            else:
                self._stream.close()
                self._stream = None

        # Reset PortAudio subsystem to flush stale AUHAL state caused by USB
        # device re-enumeration. Pa_Terminate() destroys all internal Audio Units;
        # Pa_Initialize() rebuilds them with fresh AudioObjectIDs from CoreAudio.
        # Run Pa_Terminate() in a daemon thread so a hung AUHAL cannot freeze the app.
        def _do_terminate() -> None:
            try:
                sd._terminate()
            except Exception:
                logger.warning("Pa_Terminate raised an exception; continuing")

        t = threading.Thread(target=_do_terminate, daemon=True)
        t.start()
        t.join(timeout=TERMINATE_TIMEOUT)
        if t.is_alive():
            # PortAudio's internal mutex is still held by the abandoned thread.
            # Any further Pa_Initialize / stream creation on this process will
            # deadlock. Surface this so the app can self-restart.
            raise UnrecoverableAudioError(
                f"Pa_Terminate() timed out after {TERMINATE_TIMEOUT}s"
            )

        time.sleep(0.5)  # Allow macOS to fully release CoreAudio resources
        sd._initialize()

        # Clear queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

        # Create new stream
        try:
            self._stream = self._create_stream_with_fallback()
            logger.info("Audio stream reinitialized successfully")
        except Exception:
            # Ensure we leave stream in a known state on failure
            self._stream = None
            logger.exception("Audio stream reinitialize failed")
            raise

    def stop(self) -> np.ndarray:
        """Stop recording and return audio data.

        Pauses the stream (deactivates microphone) and returns captured audio.

        Returns:
            Audio data as numpy array (int16).
        """
        self.is_recording = False

        # Pause stream (deactivates microphone)
        if self._stream is not None:
            stop_success = self._stop_with_timeout()
            if not stop_success:
                self._abort_with_timeout()

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
