"""Local edition reusing the existing recorder, hotkeys and output controls."""

import queue
import time

import numpy as np
import rumps

from .app import MIN_RECORDING_SECONDS, VoiceInputApp
from .config import save_config
from .local_models import MODELS
from .local_transcriber import LocalTranscriber
from .logger import get_logger
from .output import output_text
from .recorder import SAMPLE_RATE

logger = get_logger()


class LocalVoiceInputApp(VoiceInputApp):
    idle_title = "VoiceInput Local"

    def __init__(self, engine: LocalTranscriber, debug=False):
        self.engine = engine
        self._settings_open = False
        super().__init__(debug=debug)
        self.title = "VoiceInput Local"
        self.status_item.title = "準備完了 — 使い方はメニューから確認できます"
        self.model_item = rumps.MenuItem(
            f"音声認識モデル：{engine.key}…", callback=self._on_model_setup
        )
        self.menu.insert_before("Hotkey", self.model_item)
        self.menu.add(rumps.MenuItem("使い方・保存先…", callback=self._on_help))

    def _on_help(self, _sender):
        self._show_settings(
            lambda: rumps.alert(
                title="VoiceInput Local",
                message=(
                    "左Controlを押している間、録音します。離すと文字起こしして、"
                    "入力中のアプリへ貼り付けます。Escapeで録音を破棄できます。\n\n"
                    "Hotkey / Modeからキーや録音方法を変更できます。"
                    "文字起こし中は次の録音を開始できません。\n\n"
                    "音声認識はMac内で実行します。途中字幕には未対応です。"
                    "音声ファイルや文字起こし履歴は保存しません。"
                    "貼り付けた文字は入力先アプリとクリップボードに残ります。\n\n"
                    f"モデル保存先：{self.engine.store.root}\n"
                    "モデルのダウンロード時だけHugging Faceに接続します。"
                ),
                ok="閉じる",
            )
        )

    def _show_settings(self, callback):
        if self.recorder.is_recording or self._processing_count:
            self._notify_error("録音や文字起こしが終わってから設定を開いてください。")
            return None
        self._settings_open = True
        try:
            return callback()
        finally:
            # The modal loop pauses the event timer. Discard hotkeys pressed in
            # the dialog, without stopping/restarting macOS's event tap.
            retained = []
            try:
                while True:
                    event = self._event_queue.get_nowait()
                    if event not in {"press", "release", "cancel"}:
                        retained.append(event)
            except queue.Empty:
                pass
            for event in retained:
                self._event_queue.put(event)
            self._settings_open = False

    def _on_permission_setup(self, _sender):
        from .permission_setup import show_permission_setup

        self._show_settings(show_permission_setup)

    def _on_model_setup(self, _sender):
        from .model_setup import show_model_setup

        key = self._show_settings(
            lambda: show_model_setup(self.engine.key, self.engine.store)
        )
        if key in MODELS:
            self.engine = LocalTranscriber(key, self.engine.store)
            self._config["local_model"] = key
            save_config(self._config)
            self.model_item.title = f"音声認識モデル：{key}…"

    def _on_hotkey_press(self):
        if self._settings_open or self._processing_count:
            return
        super()._on_hotkey_press()

    def _on_hotkey_release(self):
        if not self.recorder.is_recording:
            return
        super()._on_hotkey_release()

    def _start_recording(self):
        if self._processing_count or self._settings_open:
            return
        super()._start_recording()
        # Apply the same safety limit to hold and toggle recording.
        if self.recorder.is_recording:
            self._recording_start_time = time.monotonic()
            self._auto_stopped = False
        else:
            self._is_recording = False

    def _start_realtime_overlay(self):
        # No Realtime client is constructed. Local edition never falls back to API.
        self.recorder.set_chunk_callback(None)

    def _stop_recording(self):
        if self.recorder.is_recording:
            super()._stop_recording()

    def _before_check_events(self):
        if (
            self._current_mode == "hold"
            and self.recorder.is_recording
            and self._recording_start_time is not None
            and time.monotonic() - self._recording_start_time
            >= self._max_recording_seconds
        ):
            self._stop_recording()

    def _process_audio(self, audio_data, realtime_transcriber=None):
        if self._auto_stopped:
            self._auto_stopped = False
            self._event_queue.put("status:録音上限に達しました")
            return
        if len(audio_data) == 0:
            self._event_queue.put("reinitialize")
            return
        if len(audio_data) < SAMPLE_RATE * MIN_RECORDING_SECONDS:
            self._event_queue.put("status:録音が短すぎます")
            return
        rms = np.sqrt(np.mean(audio_data.astype(np.float64) ** 2))
        if rms < self._rms_threshold:
            self._event_queue.put("status:音声が検出されませんでした")
            return
        try:
            text = self.engine.transcribe(audio_data)
            if text:
                output_text(text, mode=self._output_mode)
                self._event_queue.put("status:Ready")
            else:
                self._event_queue.put("status:音声が検出されませんでした")
        except Exception as exc:  # noqa: BLE001 - native inference worker boundary
            logger.error("Local transcription failed (%s)", type(exc).__name__)
            self._event_queue.put(f"error:文字起こしできませんでした。{exc}")
