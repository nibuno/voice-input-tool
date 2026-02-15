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
