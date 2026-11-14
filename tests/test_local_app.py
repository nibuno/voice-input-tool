import queue
from unittest.mock import Mock

import numpy as np
import pytest

from voice_input import local_app as module
from voice_input.app import VoiceInputApp
from voice_input.local_app import LocalVoiceInputApp


@pytest.fixture
def app():
    app = LocalVoiceInputApp.__new__(LocalVoiceInputApp)
    app.engine = Mock()
    app.engine.transcribe.return_value = "ローカル入力"
    app.recorder = Mock(is_recording=False)
    app._auto_stopped = False
    app._rms_threshold = 100
    app._event_queue = queue.Queue()
    app._output_mode = "copy_paste"
    app._settings_open = False
    app._processing_count = 0
    app._notify_error = Mock()
    return app


def test_offline_pipeline_outputs_local_result(app, monkeypatch):
    output = Mock()
    monkeypatch.setattr(module, "output_text", output)
    app._process_audio(np.full(16000, 1000, dtype=np.int16))
    app.engine.transcribe.assert_called_once()
    output.assert_called_once_with("ローカル入力", mode="copy_paste")
    assert list(app._event_queue.queue) == ["nekochan:happy", "status:Ready"]


def test_failed_inference_reports_error_without_output(app, monkeypatch):
    app.engine.transcribe.side_effect = RuntimeError("unavailable")
    output = Mock()
    monkeypatch.setattr(module, "output_text", output)
    app._process_audio(np.full(16000, 1000, dtype=np.int16))
    assert app._event_queue.get_nowait().startswith("error:")
    output.assert_not_called()


def test_quiet_input_does_not_infer(app):
    app._process_audio(np.zeros(16000, dtype=np.int16))
    app.engine.transcribe.assert_not_called()


def test_processing_blocks_new_recordings(app, monkeypatch):
    press = Mock()
    monkeypatch.setattr(VoiceInputApp, "_on_hotkey_press", press)
    app._processing_count = 1
    app._on_hotkey_press()
    press.assert_not_called()


def test_local_recording_does_not_construct_realtime_client(app):
    app._start_realtime_overlay()
    app.recorder.set_chunk_callback.assert_called_once_with(None)


def test_modal_discards_hotkeys_but_preserves_device_events(app):
    def dialog():
        for event in ["press", "device_change", "release", "cancel"]:
            app._event_queue.put(event)
        return "small"

    assert app._show_settings(dialog) == "small"
    assert list(app._event_queue.queue) == ["device_change"]
    assert not app._settings_open


def test_timer_callback_remains_inherited_for_rumps():
    assert LocalVoiceInputApp._check_events is VoiceInputApp._check_events


def test_local_menu_can_be_constructed_without_api_key(monkeypatch):
    from AppKit import NSApplication

    NSApplication.sharedApplication()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        VoiceInputApp, "_populate_input_device_menu", Mock(return_value=True)
    )
    instance = LocalVoiceInputApp(Mock(key="small"))
    assert instance.title == "VoiceInput Local"
    assert "音声認識モデル：small…" in instance.menu
    assert "使い方・保存先…" in instance.menu
    assert "Show Nekochan" in instance.menu
