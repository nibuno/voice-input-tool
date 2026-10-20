"""Permission setup must not interrupt either recording mode or any worker."""

import queue
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from voice_input import app as app_module
from voice_input.app import VoiceInputApp
from voice_input.pet import DesktopPet


@pytest.fixture
def app():
    instance = VoiceInputApp.__new__(VoiceInputApp)
    instance.recorder = Mock(is_recording=False)
    instance.hotkey_listener = Mock()
    instance._notify_error = Mock()
    instance._is_recording = False
    instance._processing_count = 0
    instance._pet = DesktopPet()
    instance._pet_show_pending = False
    instance._current_mode = "hold"
    instance._auto_stopped = False
    instance._debug = False
    instance._rms_threshold = 100
    instance._event_queue = queue.Queue()
    instance._stop_realtime_overlay = Mock(return_value=None)
    instance.status_item = Mock()
    return instance


@pytest.fixture
def show_setup(monkeypatch):
    show = Mock(return_value=True)
    monkeypatch.setitem(
        sys.modules, "voice_input.permission_setup",
        SimpleNamespace(show_permission_setup=show),
    )
    return show


@pytest.mark.parametrize("mode", ["hold", "toggle"])
def test_setup_during_recording_keeps_listener_running(app, show_setup, mode):
    app._current_mode = mode
    app.recorder.is_recording = True
    app._is_recording = mode == "toggle"

    app._on_permission_setup(None)

    show_setup.assert_not_called()
    app.hotkey_listener.stop.assert_not_called()
    app._notify_error.assert_called_once()


def test_setup_during_processing_uses_state_not_title(app, show_setup):
    app._processing_count = 1
    # Another queued status update can replace the title before work finishes.
    app.title = "Voice Input"

    app._on_permission_setup(None)

    show_setup.assert_not_called()
    app.hotkey_listener.stop.assert_not_called()


def test_stale_toggle_flag_does_not_block_setup(app, show_setup):
    # Starting the recorder can fail after the toggle flag was set.
    app._is_recording = True
    app.recorder.is_recording = False
    app._on_permission_setup(None)
    show_setup.assert_called_once_with()


@pytest.mark.parametrize("raises", [False, True])
def test_idle_setup_keeps_listener_running(app, show_setup, raises):
    calls = []
    app.hotkey_listener.stop.side_effect = lambda: calls.append("stop")
    app.hotkey_listener.start.side_effect = lambda: calls.append("start")

    def show():
        calls.append("show")
        if raises:
            raise RuntimeError("window creation failed")

    show_setup.side_effect = show
    if raises:
        with pytest.raises(RuntimeError):
            app._on_permission_setup(None)
    else:
        app._on_permission_setup(None)
    assert calls == ["show"]
    show_setup.assert_called_once_with()


def test_setup_waits_for_all_processing_workers(app, show_setup, monkeypatch):
    thread = Mock()
    monkeypatch.setattr(app_module.threading, "Thread", thread)
    app._process_audio = Mock()

    app._stop_recording()
    app._stop_recording()
    assert app._processing_count == 2
    workers = thread.call_args_list
    assert all(call.kwargs["target"] == app._process_audio_worker for call in workers)

    workers[0].kwargs["target"](*workers[0].kwargs["args"])
    app._check_events(None)
    assert app._processing_count == 1
    app._on_permission_setup(None)
    show_setup.assert_not_called()

    workers[1].kwargs["target"](*workers[1].kwargs["args"])
    app._check_events(None)
    assert app._processing_count == 0
    app._on_permission_setup(None)
    show_setup.assert_called_once()


@pytest.mark.parametrize("case", ["auto_stop", "empty", "short", "quiet", "error"])
def test_early_returns_and_errors_release_processing_guard(
    app, case, monkeypatch, tmp_path,
):
    audio = np.zeros(8000, dtype=np.int16)
    if case == "auto_stop":
        app._auto_stopped = True
    elif case == "empty":
        audio = audio[:0]
    elif case == "short":
        audio = audio[:10]
    elif case == "error":
        audio[:] = 500
        monkeypatch.setattr(app_module, "save_audio", lambda _: tmp_path / "audio.wav")
        monkeypatch.setattr(
            app_module, "transcribe", Mock(side_effect=ValueError("bad response"))
        )
    app._processing_count = 1

    app._process_audio_worker(audio)
    events = list(app._event_queue.queue)
    assert events[-1] == "processing_finished"
    # Only inspect the completion event here; audio recovery is tested separately.
    app._event_queue = queue.Queue()
    app._event_queue.put("processing_finished")
    app._check_events(None)
    assert app._processing_count == 0


def test_unexpected_worker_exception_still_reports_completion(app):
    app._process_audio = Mock(side_effect=RuntimeError("unexpected failure"))
    with pytest.raises(RuntimeError):
        app._process_audio_worker(np.zeros(1))
    assert app._event_queue.get_nowait() == "processing_finished"


def test_worker_start_failure_does_not_leave_setup_blocked(app, monkeypatch):
    thread = Mock()
    thread.return_value.start.side_effect = RuntimeError("cannot create thread")
    monkeypatch.setattr(app_module.threading, "Thread", thread)

    app._stop_recording()

    assert app._processing_count == 0
    assert app._event_queue.get_nowait().startswith("error:")
