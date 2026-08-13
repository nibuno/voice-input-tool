"""Best-effort Realtime API transcription for the recording overlay."""

from __future__ import annotations

import base64
import os
import queue
import threading
import time
from collections.abc import Callable

import numpy as np
from openai import OpenAI
from scipy.signal import resample_poly

from .logger import get_logger
from .recorder import SAMPLE_RATE

logger = get_logger()

REALTIME_SAMPLE_RATE = 24000
REALTIME_TRANSCRIPTION_MODEL = "gpt-realtime-whisper"
SEND_BATCH_SAMPLES = SAMPLE_RATE // 10  # 100 ms at the recorder sample rate
MIN_COMMIT_SAMPLES = SAMPLE_RATE // 10
STOP_GRACE_SECONDS = 3.0
FINAL_TRANSCRIPT_TIMEOUT_SECONDS = STOP_GRACE_SECONDS + 0.5
MAX_QUEUED_CHUNKS = 4096
_STOP = object()


class TranscriptState:
    """Accumulate finalized utterances and the current partial utterance."""

    def __init__(self) -> None:
        self.committed = ""
        self.partial = ""

    @property
    def display_text(self) -> str:
        return " ".join(part for part in (self.committed, self.partial) if part).strip()

    def add_delta(self, delta: str) -> str:
        self.partial += delta
        return self.display_text

    def complete(self, transcript: str) -> str:
        text = transcript.strip()
        if text:
            self.committed = " ".join(
                part for part in (self.committed, text) if part
            )
        self.partial = ""
        return self.display_text


class RealtimeTranscriber:
    """Stream recorder chunks to OpenAI without affecting final transcription."""

    def __init__(
        self,
        on_text: Callable[[str], None],
        on_error: Callable[[str], None] | None = None,
        on_done: Callable[[], None] | None = None,
        client_factory: Callable[[], OpenAI] | None = None,
    ) -> None:
        self._on_text = on_text
        self._on_error = on_error
        self._on_done = on_done
        self._client_factory = client_factory or self._default_client
        self._audio_queue: queue.Queue[np.ndarray | object] = queue.Queue(
            maxsize=MAX_QUEUED_CHUNKS
        )
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._connection = None
        self._connection_lock = threading.Lock()
        self._dropped_chunks = 0
        self._stopping = threading.Event()
        self._result_ready = threading.Event()
        self._result_lock = threading.Lock()
        self._final_transcript = ""

    @staticmethod
    def _default_client() -> OpenAI:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        return OpenAI(api_key=api_key)

    def start(self) -> None:
        """Start a fresh realtime transcription session."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._drain_audio_queue()
        self._stop_event.clear()
        self._stopping.clear()
        self._result_ready.clear()
        with self._result_lock:
            self._final_transcript = ""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def submit(self, chunk: np.ndarray) -> None:
        """Queue an audio chunk without blocking PortAudio's callback thread."""
        if self._stop_event.is_set() or self._stopping.is_set():
            return
        try:
            self._audio_queue.put_nowait(chunk.copy())
        except queue.Full:
            # This runs on PortAudio's callback thread. Never log or block here.
            self._dropped_chunks += 1

    def stop(self) -> None:
        """Finish queued audio and close after final transcript events arrive."""
        if self._stopping.is_set():
            return
        self._stopping.set()
        try:
            self._audio_queue.put_nowait(_STOP)
        except queue.Full:
            pass
        threading.Thread(target=self._close_after_grace, daemon=True).start()

    def close(self) -> None:
        """Close immediately during application teardown."""
        self._stop_event.set()
        self._close_connection()

    def wait_for_final_transcript(
        self,
        timeout: float = FINAL_TRANSCRIPT_TIMEOUT_SECONDS,
    ) -> str | None:
        """Return the committed Realtime transcript, or None for fallback."""
        if not self._result_ready.wait(timeout):
            logger.warning("Realtime final transcript timed out")
            return None
        with self._result_lock:
            text = self._final_transcript.strip()
        return text or None

    def _close_after_grace(self) -> None:
        time.sleep(STOP_GRACE_SECONDS)
        self.close()

    def _close_connection(self) -> None:
        with self._connection_lock:
            connection = self._connection
        if connection is None:
            return
        try:
            connection.close()
        except Exception:  # noqa: BLE001 - close is best effort at boundary
            logger.debug("Realtime connection was already closed", exc_info=True)

    def _drain_audio_queue(self) -> None:
        while True:
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                return

    def _run(self) -> None:
        state = TranscriptState()
        try:
            client = self._client_factory()
            with client.realtime.connect(
                extra_query={"intent": "transcription"}
            ) as connection:
                with self._connection_lock:
                    self._connection = connection
                connection.session.update(session=self._session_config())
                logger.info("Realtime transcription connected")
                sender = threading.Thread(
                    target=self._send_audio,
                    args=(connection,),
                    daemon=True,
                )
                sender.start()

                for event in connection:
                    if self._stop_event.is_set():
                        break
                    event_type = getattr(event, "type", "")
                    if event_type == (
                        "conversation.item.input_audio_transcription.delta"
                    ):
                        delta = getattr(event, "delta", "") or ""
                        if delta:
                            logger.debug("Realtime transcription delta: %s", delta)
                            self._on_text(state.add_delta(delta))
                    elif event_type == (
                        "conversation.item.input_audio_transcription.completed"
                    ):
                        transcript = getattr(event, "transcript", "") or ""
                        logger.info(
                            "Realtime transcription completed: %s", transcript
                        )
                        completed_text = state.complete(transcript)
                        with self._result_lock:
                            self._final_transcript = completed_text
                        self._result_ready.set()
                        self._on_text(completed_text)
                    elif event_type == "error":
                        error = getattr(event, "error", None)
                        raise RuntimeError(f"Realtime API error: {error}")
        except Exception as exc:  # noqa: BLE001 - network failures are optional
            self._result_ready.set()
            if not self._stop_event.is_set():
                logger.warning("Realtime transcription unavailable: %s", exc)
                if self._on_error is not None:
                    self._on_error(str(exc))
        finally:
            self._result_ready.set()
            with self._connection_lock:
                self._connection = None
            if self._on_done is not None:
                self._on_done()

    def _send_audio(self, connection) -> None:
        sent_samples = 0
        while not self._stop_event.is_set():
            batch = self._next_audio_batch()
            if batch is None:
                if sent_samples >= MIN_COMMIT_SAMPLES:
                    connection.input_audio_buffer.commit()
                    logger.debug(
                        "Realtime audio turn committed on stop (%.2fs)",
                        sent_samples / SAMPLE_RATE,
                    )
                return
            if len(batch) == 0:
                continue
            try:
                connection.input_audio_buffer.append(
                    audio=self._encode_chunk(batch)
                )
                sent_samples += len(batch)
            except Exception as exc:  # noqa: BLE001 - sender must fail closed
                if not self._stop_event.is_set():
                    logger.warning("Failed to send realtime audio: %s", exc)
                return

    def _next_audio_batch(self) -> np.ndarray | None:
        """Combine tiny PortAudio callbacks into an efficient send-sized batch."""
        try:
            first = self._audio_queue.get(timeout=0.2)
        except queue.Empty:
            return np.empty(0, dtype=np.int16)
        if first is _STOP:
            return None

        chunks = [np.asarray(first, dtype=np.int16).reshape(-1)]
        sample_count = len(chunks[0])
        while sample_count < SEND_BATCH_SAMPLES:
            try:
                chunk = self._audio_queue.get_nowait()
            except queue.Empty:
                break
            if chunk is _STOP:
                self._audio_queue.put_nowait(_STOP)
                break
            flattened = np.asarray(chunk, dtype=np.int16).reshape(-1)
            chunks.append(flattened)
            sample_count += len(flattened)
        return np.concatenate(chunks)

    @staticmethod
    def _encode_chunk(chunk: np.ndarray) -> str:
        mono = np.asarray(chunk, dtype=np.int16).reshape(-1)
        if SAMPLE_RATE != REALTIME_SAMPLE_RATE:
            mono = resample_poly(mono, REALTIME_SAMPLE_RATE, SAMPLE_RATE)
            mono = np.clip(mono, -32768, 32767).astype(np.int16)
        return base64.b64encode(mono.tobytes()).decode("ascii")

    @staticmethod
    def _session_config() -> dict:
        return {
            "type": "transcription",
            "audio": {
                "input": {
                    "format": {"type": "audio/pcm", "rate": REALTIME_SAMPLE_RATE},
                    "noise_reduction": {"type": "near_field"},
                    "transcription": {
                        "model": REALTIME_TRANSCRIPTION_MODEL,
                        "language": "ja",
                    },
                    # gpt-realtime-whisper requires turn detection to be null.
                    # Audio is streamed continuously and committed once on stop.
                    "turn_detection": None,
                }
            },
        }
