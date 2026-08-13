"""Tests for the recorder's best-effort audio chunk observer."""

from unittest.mock import Mock

import numpy as np

from voice_input.recorder import StreamingRecorder


def test_audio_callback_notifies_chunk_observer_while_recording() -> None:
    recorder = StreamingRecorder()
    observer = Mock()
    recorder.set_chunk_callback(observer)
    recorder.is_recording = True
    chunk = np.array([[1], [2]], dtype=np.int16)

    recorder._audio_callback(
        chunk, len(chunk), object(), Mock(__bool__=lambda _: False)
    )

    observed = observer.call_args.args[0]
    np.testing.assert_array_equal(observed, chunk)
    assert observed is not chunk


def test_audio_callback_ignores_observer_errors() -> None:
    recorder = StreamingRecorder()
    recorder.set_chunk_callback(Mock(side_effect=RuntimeError("boom")))
    recorder.is_recording = True
    chunk = np.array([[1]], dtype=np.int16)

    recorder._audio_callback(
        chunk, len(chunk), object(), Mock(__bool__=lambda _: False)
    )

    buffered = recorder._queue.get_nowait()
    np.testing.assert_array_equal(buffered, chunk)
