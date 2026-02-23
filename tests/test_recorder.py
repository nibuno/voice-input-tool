"""Tests for recorder module."""

import time

import sounddevice as sd

import voice_input.recorder as recorder_module
from voice_input.recorder import StreamingRecorder


class DummyStream:
    def start(self):
        return None

    def stop(self):
        return None

    def abort(self):
        return None

    def close(self):
        return None


def test_initialize_passes_device(monkeypatch):
    calls = []

    def fake_inputstream(*_args, **kwargs):
        calls.append(kwargs.get("device"))
        return DummyStream()

    monkeypatch.setattr(sd, "InputStream", fake_inputstream)

    recorder = StreamingRecorder()
    recorder.set_device(2)
    recorder.initialize()

    assert calls == [2]


def test_reinitialize_passes_device(monkeypatch):
    calls = []

    def fake_inputstream(*_args, **kwargs):
        calls.append(kwargs.get("device"))
        return DummyStream()

    monkeypatch.setattr(sd, "InputStream", fake_inputstream)

    recorder = StreamingRecorder()
    recorder.set_device(1)
    recorder.initialize()
    recorder.set_device(3)
    recorder.reinitialize()

    assert calls[-1] == 3


def test_reinitialize_falls_back_to_default_on_failure(monkeypatch):
    calls = []
    first_call = True

    def fake_inputstream(*_args, **kwargs):
        nonlocal first_call
        calls.append(kwargs.get("device"))
        if first_call:
            first_call = False
            raise sd.PortAudioError("fail", -1)
        return DummyStream()

    monkeypatch.setattr(sd, "InputStream", fake_inputstream)

    recorder = StreamingRecorder()
    recorder.set_device(4)
    recorder.reinitialize()

    assert calls == [4, None]


class HangingAbortStream(DummyStream):
    def abort(self):
        while True:
            time.sleep(0.1)


def test_reinitialize_proceeds_with_pa_terminate_when_abort_times_out(monkeypatch):
    """abort() timeout: close() must be skipped to avoid a second hang.

    When abort() times out the AUHAL callback thread is stuck (e.g. device
    physically disconnected).  close() internally calls Pa_CloseStream() which
    waits for the callback thread — it would hang just like abort().
    The correct path is to skip close() and let Pa_Terminate() forcibly clean up.
    """
    closed = {"count": 0}
    terminated = {"count": 0}
    initialized = {"count": 0}

    original_close = HangingAbortStream.close

    def fake_close(self):
        closed["count"] += 1

    HangingAbortStream.close = fake_close

    def fake_terminate():
        terminated["count"] += 1

    def fake_initialize():
        initialized["count"] += 1

    monkeypatch.setattr(recorder_module, "ABORT_TIMEOUT", 0.01)
    monkeypatch.setattr(recorder_module, "TERMINATE_TIMEOUT", 0.5)
    monkeypatch.setattr(sd, "_terminate", fake_terminate)
    monkeypatch.setattr(sd, "_initialize", fake_initialize)
    monkeypatch.setattr(sd, "InputStream", lambda *a, **kw: DummyStream())

    recorder = StreamingRecorder()
    recorder._stream = HangingAbortStream()

    recorder.reinitialize()

    HangingAbortStream.close = original_close

    assert closed["count"] == 0, "stream.close() must NOT be called after abort timeout (would hang)"
    assert terminated["count"] == 1, "Pa_Terminate() must be called even after abort timeout"
    assert initialized["count"] == 1, "Pa_Initialize() must be called after Pa_Terminate()"
    assert recorder._stream is not None, "new stream must be created after reinitialize"


class HangingStopStream(DummyStream):
    def stop(self):
        while True:
            time.sleep(0.1)


def test_stop_falls_back_to_abort_when_stream_stop_times_out(monkeypatch):
    recorder = StreamingRecorder()
    recorder._stream = HangingStopStream()
    recorder.is_recording = True

    monkeypatch.setattr(recorder_module, "STOP_TIMEOUT", 0.01)

    called = {"abort": 0}

    def fake_abort_with_timeout():
        called["abort"] += 1
        return True

    monkeypatch.setattr(recorder, "_abort_with_timeout", fake_abort_with_timeout)

    start = time.monotonic()
    audio = recorder.stop()
    elapsed = time.monotonic() - start

    assert called["abort"] == 1
    assert elapsed < 0.2
    assert audio.size == 0
