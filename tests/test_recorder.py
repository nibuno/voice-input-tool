"""Tests for recorder module."""

import sounddevice as sd

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
