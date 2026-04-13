"""Mac menu bar application for voice input."""

import atexit
import queue
import threading
import time

import numpy as np
import openai
import rumps
import sounddevice as sd

from .accessibility import check_accessibility_permission
from .config import load_config, save_config
from .device_monitor import DeviceMonitor
from .hotkey import HOTKEY_NAMES, HotkeyListener
from .logger import get_logger
from .output import output_text
from .recorder import (
    SAMPLE_RATE,
    StreamingRecorder,
    UnrecoverableAudioError,
    save_audio,
)
from .restart import schedule_self_restart
from .transcriber import transcribe

logger = get_logger()

# Minimum recording duration in seconds
MIN_RECORDING_SECONDS = 0.3

# Minimum RMS (root mean square) amplitude to consider as speech
# int16 audio ranges from -32768 to 32767
# This threshold filters out silence and very quiet recordings
MIN_RMS_THRESHOLD = 100

# If the audio callback has not fired for this many seconds while we believe
# we're recording, treat the stream as hung (AUHAL thread stuck) and force
# a stop + reinitialize. Sized to be well above normal scheduling jitter.
CALLBACK_STALL_THRESHOLD_SEC = 2.0

# Recording mode names for menu display
MODE_NAMES = {
    "hold": "Hold (押している間)",
    "toggle": "Toggle (押すたびに切替)",
}


class VoiceInputApp(rumps.App):
    """Mac menu bar application for voice input using Whisper API."""

    def __init__(self, debug: bool = False) -> None:
        super().__init__(
            name="Voice Input",
            title="Voice Input",
        )

        self._debug = debug

        # Load config
        self._config = load_config()
        self._current_hotkey = self._config.get("hotkey", "ctrl_l")
        self._current_mode = self._config.get("mode", "hold")
        self._rms_threshold = self._config.get("rms_threshold", MIN_RMS_THRESHOLD)
        self._current_input_device_name = self._config.get("input_device")
        self._max_recording_seconds = self._config.get("max_recording_seconds", 30.0)

        # Toggle mode state
        self._is_recording = False
        self._recording_start_time: float | None = None
        self._last_timeout_log_second: int | None = None
        self._auto_stopped = False

        self.recorder = StreamingRecorder()
        self._event_queue: queue.Queue[str] = queue.Queue()
        self._reinit_lock = threading.Lock()
        self._device_monitor: DeviceMonitor | None = None
        self._configured_device_available: bool = True

        self.hotkey_listener = HotkeyListener(
            on_press=lambda: self._event_queue.put("press"),
            on_release=lambda: self._event_queue.put("release"),
            hotkey=self._current_hotkey,
        )

        # Menu items
        self.status_item = rumps.MenuItem("Status: Ready")

        # Hotkey submenu
        self.hotkey_menu = rumps.MenuItem("Hotkey")
        self._hotkey_items = {}
        for key_id, key_name in HOTKEY_NAMES.items():
            item = rumps.MenuItem(key_name, callback=self._on_hotkey_selected)
            item.key_id = key_id  # Store key_id for callback
            if key_id == self._current_hotkey:
                item.state = 1  # Checkmark
            self._hotkey_items[key_id] = item
            self.hotkey_menu.add(item)

        # Mode submenu
        self.mode_menu = rumps.MenuItem("Mode")
        self._mode_items = {}
        for mode_id, mode_name in MODE_NAMES.items():
            item = rumps.MenuItem(mode_name, callback=self._on_mode_selected)
            item.mode_id = mode_id  # Store mode_id for callback
            if mode_id == self._current_mode:
                item.state = 1  # Checkmark
            self._mode_items[mode_id] = item
            self.mode_menu.add(item)

        # Input device submenu
        self.input_device_menu = rumps.MenuItem("Input Device")
        self._input_device_items = {}
        self._input_device_menu_populated = False

        self.menu = [
            self.status_item,
            None,  # Separator
            self.hotkey_menu,
            self.mode_menu,
            self.input_device_menu,
            rumps.MenuItem("Language: Japanese"),
        ]
        self._input_device_menu_populated = self._populate_input_device_menu()

    def _on_hotkey_selected(self, sender: rumps.MenuItem) -> None:
        """Handle hotkey selection from menu."""
        key_id = sender.key_id

        # Update checkmarks
        for item in self._hotkey_items.values():
            item.state = 0
        sender.state = 1

        # Update hotkey listener
        self._current_hotkey = key_id
        self.hotkey_listener.set_hotkey(key_id)

        # Save config
        self._config["hotkey"] = key_id
        save_config(self._config)

    def _on_mode_selected(self, sender: rumps.MenuItem) -> None:
        """Handle mode selection from menu."""
        mode_id = sender.mode_id

        # Update checkmarks
        for item in self._mode_items.values():
            item.state = 0
        sender.state = 1

        # Update mode and reset recording state
        self._current_mode = mode_id
        self._is_recording = False

        # Save config
        self._config["mode"] = mode_id
        save_config(self._config)
        logger.info(f"App: Mode changed to {mode_id}")

    def _populate_input_device_menu(self) -> None:
        """Populate input device submenu from current device list."""
        if getattr(self.input_device_menu, "_menu", None) is not None:
            self.input_device_menu.clear()
        self._input_device_items = {}

        refresh_item = rumps.MenuItem("Refresh Devices", callback=self._on_refresh_devices)
        self.input_device_menu.add(refresh_item)
        self.input_device_menu.add(None)

        # System default option
        default_item = rumps.MenuItem("System Default", callback=self._on_input_device_selected)
        default_item.device_name = None
        if self._current_input_device_name is None:
            default_item.state = 1
        self._input_device_items[None] = default_item
        self.input_device_menu.add(default_item)

        for dev in self._list_input_devices():
            name = dev["name"]
            item = rumps.MenuItem(name, callback=self._on_input_device_selected)
            item.device_name = name
            if name == self._current_input_device_name:
                item.state = 1
            self._input_device_items[name] = item
            self.input_device_menu.add(item)
        return True

    @rumps.timer(0.5)
    def _ensure_input_device_menu(self, sender: rumps.Timer) -> None:
        """Populate input device menu once after app menu is attached."""
        if self._input_device_menu_populated:
            sender.stop()
            return
        self._input_device_menu_populated = self._populate_input_device_menu()
        if self._input_device_menu_populated:
            sender.stop()

    def _on_refresh_devices(self, _sender: rumps.MenuItem) -> None:
        """Refresh the input device list."""
        self._populate_input_device_menu()

    def _on_input_device_selected(self, sender: rumps.MenuItem) -> None:
        """Handle input device selection from menu."""
        if self.recorder.is_recording:
            self._event_queue.put("status:Recording (device change blocked)")
            return

        device_name = sender.device_name

        for item in self._input_device_items.values():
            item.state = 0
        sender.state = 1

        self._current_input_device_name = device_name
        self._config["input_device"] = device_name
        save_config(self._config)

        device_index = self._resolve_input_device_index(device_name)
        self.recorder.set_device(device_index)

        try:
            if self.recorder.is_initialized:
                self.recorder.reinitialize()
            self._event_queue.put("status:Ready (device updated)")
        except UnrecoverableAudioError as e:
            logger.error(f"App: Unrecoverable audio state on device switch: {e}")
            self._notify_error("デバイス切替時に音声ストリーム復旧不能、再起動します")
            schedule_self_restart(f"device switch reinit: {e}")
        except (RuntimeError, sd.PortAudioError) as e:
            logger.exception(f"App: Failed to reinitialize with device: {e}")
            self._event_queue.put(f"error:{e}")

    def _list_input_devices(self) -> list[dict]:
        """Return a list of input-capable devices."""
        devices = sd.query_devices()
        return [dev for dev in devices if dev.get("max_input_channels", 0) > 0]

    def _resolve_input_device_index(self, device_name: str | None) -> int | None:
        """Resolve device name to current index; None means OS default."""
        if device_name is None:
            return None
        for index, dev in enumerate(sd.query_devices()):
            if dev.get("max_input_channels", 0) > 0 and dev.get("name") == device_name:
                return index
        logger.warning(f"App: Input device not found: {device_name}")
        return None

    @rumps.timer(0.05)
    def _check_events(self, _sender: object) -> None:
        """Poll for hotkey events from the queue."""
        # Detect a silently-stalled audio callback (e.g., AUHAL thread hung
        # without any sleep/device-change notification). If we believe we're
        # recording but no sample has arrived for a while, abort and reinit.
        if self._is_recording and self.recorder.is_recording:
            idle = self.recorder.seconds_since_last_callback()
            if idle is not None and idle > CALLBACK_STALL_THRESHOLD_SEC:
                logger.warning(
                    "App: Audio callback stalled for %.1fs — forcing stop + reinit",
                    idle,
                )
                self._auto_stopped = True
                self._is_recording = False
                self._stop_recording()
                self._event_queue.put("status:Ready (recovered from stall)")
                self._event_queue.put("reinitialize")
                return

        # Auto-stop for toggle mode if recording exceeds max duration
        if (
            self._current_mode == "toggle"
            and self._is_recording
            and self._recording_start_time is not None
            and self._max_recording_seconds > 0
        ):
            elapsed = time.monotonic() - self._recording_start_time
            elapsed_sec = int(elapsed)
            if self._last_timeout_log_second != elapsed_sec:
                self._last_timeout_log_second = elapsed_sec
                logger.debug(
                    "App: Recording elapsed %.1fs / %.1fs",
                    elapsed,
                    self._max_recording_seconds,
                )
            if elapsed >= self._max_recording_seconds:
                logger.info("App: Auto-stopping recording due to timeout")
                self._auto_stopped = True
                self._is_recording = False
                self._stop_recording()
                self._event_queue.put("status:Ready (auto-stopped)")
        try:
            while True:
                event = self._event_queue.get_nowait()
                if event == "press":
                    self._on_hotkey_press()
                elif event == "release":
                    self._on_hotkey_release()
                elif event == "reinitialize":
                    threading.Thread(
                        target=self._reinitialize_audio, daemon=True
                    ).start()
                elif event == "system_wake":
                    threading.Thread(
                        target=self._reinit_after_wake, daemon=True
                    ).start()
                elif event == "device_change":
                    threading.Thread(
                        target=self._handle_device_change, daemon=True
                    ).start()
                elif event.startswith("device_disconnected:"):
                    device_name = event[len("device_disconnected:"):]
                    self.title = "Voice Input"
                    self.status_item.title = "Status: Ready (default mic)"
                    self._notify_error(
                        f"マイク「{device_name}」が切断されました。"
                        "システムデフォルトを使用します。"
                    )
                elif event.startswith("device_reconnected:"):
                    device_name = event[len("device_reconnected:"):]
                    self.title = "Voice Input"
                    self.status_item.title = "Status: Ready"
                    logger.info(f"App: '{device_name}' reconnected and ready")
                elif event.startswith("status:"):
                    status = event[7:]
                    self.title = "Voice Input"
                    self.status_item.title = f"Status: {status}"
                elif event.startswith("error:"):
                    message = event[6:]
                    self.title = "Voice Input"
                    self.status_item.title = "Status: Error"
                    self._notify_error(message)
        except queue.Empty:
            # No events in queue; return to the timer loop.
            return

    def _reinitialize_audio(self) -> None:
        """Reinitialize audio stream in a dedicated thread.

        Called when an empty recording buffer indicates a stale stream
        (e.g., after USB device re-enumeration on sleep/wake).
        The 0.5s Pa_Terminate/Initialize delay runs here, off the main thread.
        """
        acquired = self._reinit_lock.acquire(blocking=False)
        if not acquired:
            logger.debug("App: Reinitialize already in progress, skipping")
            self._event_queue.put("status:Ready (retry recording)")
            return
        try:
            # Re-resolve device index from name; index may change after USB re-enumeration
            device_index = self._resolve_input_device_index(self._current_input_device_name)
            self.recorder.set_device(device_index)
            self.recorder.reinitialize()
            self._event_queue.put("status:Ready (retry recording)")
        except UnrecoverableAudioError as e:
            logger.error(f"App: Unrecoverable audio state: {e} — self-restart")
            self._notify_error("音声ストリームが復旧不能のため再起動します")
            schedule_self_restart(f"reinit: {e}")
        except (RuntimeError, sd.PortAudioError) as e:
            logger.exception(f"App: Failed to reinitialize audio stream: {e}")
            self._event_queue.put(f"error:Audio reinit failed: {e}")
        finally:
            self._reinit_lock.release()

    # ------------------------------------------------------------------
    # Sleep / wake / device change handlers
    # ------------------------------------------------------------------

    def _on_system_sleep(self) -> None:
        """Called when the system is about to sleep (main thread).

        Cleans up the audio stream so macOS can fully power down USB devices.
        """
        logger.info("App: System will sleep - cleaning up audio stream")
        if self._is_recording:
            self._is_recording = False
            self._auto_stopped = True
            self._recording_start_time = None
            self.recorder.is_recording = False
        self.recorder.cleanup()
        self.title = "Voice Input"
        self.status_item.title = "Status: Sleeping..."

    def _on_system_wake(self) -> None:
        """Called when the system woke from sleep (main thread).

        Schedules audio reinitialize via event queue so the 1.5 s wait
        and Pa_Terminate/Initialize run off the main thread.
        """
        logger.info("App: System woke - scheduling audio reinitialize")
        self._event_queue.put("system_wake")

    def _on_audio_device_change(self) -> None:
        """Called when the CoreAudio device list changes (background thread).

        Debounced by DeviceMonitor; routes handling through the event queue.
        """
        logger.info("App: Audio device list changed")
        self._event_queue.put("device_change")

    def _reinit_after_wake(self) -> None:
        """Reinitialize audio stream after system wake (background thread).

        Waits for CoreAudio and USB devices to stabilize before rebuilding
        the PortAudio context.
        """
        acquired = self._reinit_lock.acquire(blocking=False)
        if not acquired:
            logger.debug("App: Reinitialize already in progress, skipping wake reinit")
            return
        try:
            time.sleep(1.5)  # Wait for CoreAudio/USB to fully stabilize after wake
            device_index = self._resolve_input_device_index(self._current_input_device_name)
            self.recorder.set_device(device_index)
            self.recorder.reinitialize()
            self._event_queue.put("status:Ready")
            logger.info("App: Audio stream ready after wake")
        except UnrecoverableAudioError as e:
            logger.error(f"App: Unrecoverable audio state after wake: {e} — self-restart")
            self._notify_error("復帰後に音声ストリーム復旧不能、再起動します")
            schedule_self_restart(f"wake reinit: {e}")
        except Exception as e:
            logger.exception(f"App: Failed to reinitialize after wake: {e}")
            self._event_queue.put(f"error:Wake reinit failed: {e}")
        finally:
            self._reinit_lock.release()

    def _handle_device_change(self) -> None:
        """Handle CoreAudio device list change (background thread).

        Re-resolves the configured device by name. On disconnect, falls back
        to OS default and notifies the user. On reconnect, switches back.
        """
        acquired = self._reinit_lock.acquire(blocking=False)
        if not acquired:
            logger.debug("App: Reinitialize already in progress, skipping device change")
            return
        try:
            if self._current_input_device_name is None:
                return  # Using OS default; no specific device to track

            # Resolve availability first so the flag is always up-to-date,
            # even when we defer the actual reinitialize due to recording.
            new_index = self._resolve_input_device_index(self._current_input_device_name)
            was_available = self._configured_device_available
            self._configured_device_available = new_index is not None

            if self.recorder.is_recording or self._is_recording:
                logger.info("App: Recording in progress, deferring device change handling")
                return

            if not self._configured_device_available:
                # Configured device disconnected → fall back to OS default
                logger.info(f"App: '{self._current_input_device_name}' disconnected")
                self.recorder.set_device(None)
                if self.recorder.is_initialized:
                    try:
                        self.recorder.reinitialize()
                    except UnrecoverableAudioError as e:
                        logger.error(f"App: Unrecoverable audio state on disconnect: {e}")
                        schedule_self_restart(f"disconnect reinit: {e}")
                        return
                    except Exception as e:
                        logger.warning(f"App: Reinitialize after disconnect failed: {e}")
                if was_available:
                    self._event_queue.put(
                        f"device_disconnected:{self._current_input_device_name}"
                    )
            else:
                # Configured device is present (reconnected or index changed)
                self.recorder.set_device(new_index)
                if self.recorder.is_initialized:
                    try:
                        self.recorder.reinitialize()
                    except UnrecoverableAudioError as e:
                        logger.error(f"App: Unrecoverable audio state on reconnect: {e}")
                        schedule_self_restart(f"reconnect reinit: {e}")
                        return
                    except Exception as e:
                        logger.warning(f"App: Reinitialize after reconnect failed: {e}")
                if not was_available:
                    # Device just came back
                    self._event_queue.put(
                        f"device_reconnected:{self._current_input_device_name}"
                    )
        finally:
            self._reinit_lock.release()

    def _notify_error(self, message: str) -> None:
        """Show an error notification if available; fall back to logs."""
        try:
            rumps.notification(
                title="Voice Input Error",
                subtitle="",
                message=message,
            )
        except Exception as e:
            logger.warning(f"App: Notification failed: {e}")

    def _on_hotkey_press(self) -> None:
        """Handle hotkey press based on current mode."""
        if self._current_mode == "toggle":
            if self._is_recording:
                self._is_recording = False
                self._stop_recording()
            else:
                self._is_recording = True
                self._start_recording()
        else:  # hold mode
            self._start_recording()

    def _on_hotkey_release(self) -> None:
        """Handle hotkey release based on current mode."""
        if self._current_mode == "hold":
            self._stop_recording()

    def _start_recording(self) -> None:
        """Start recording audio."""
        logger.info("App: Start recording triggered")

        if not self.recorder.is_initialized:
            logger.warning("App: Recorder not initialized, attempting initialize")
            try:
                self.recorder.initialize()
            except (RuntimeError, sd.PortAudioError) as e:
                logger.exception(f"App: Recorder initialize failed: {e}")
                self._event_queue.put("error:Audio stream not initialized")
                return

        try:
            self.title = "Recording..."
            self.status_item.title = "Status: Recording..."
            self.recorder.start()
            if self._current_mode == "toggle":
                self._recording_start_time = time.monotonic()
                self._last_timeout_log_second = None
                self._auto_stopped = False
                logger.info(
                    "App: Auto-stop enabled (%.1fs)",
                    self._max_recording_seconds,
                )
        except (RuntimeError, sd.PortAudioError) as e:
            logger.exception(f"App: Failed to start recording: {e}")
            # Attempt reinitialize once (device may be stale after idle/sleep)
            try:
                self.recorder.reinitialize()
                self.recorder.start()
                logger.info("App: Recording started after reinitialize")
                return
            except (RuntimeError, sd.PortAudioError) as reinit_err:
                logger.exception(
                    f"App: Failed to reinitialize/start recording: {reinit_err}"
                )
                self._event_queue.put(f"error:{reinit_err}")

    def _stop_recording(self) -> None:
        """Stop recording and process audio."""
        logger.info("App: Stop recording triggered")
        self._recording_start_time = None
        try:
            audio_data = self.recorder.stop()
            self.title = "Processing..."
            self.status_item.title = "Status: Processing..."

            # Process in background thread
            logger.debug("App: Starting audio processing thread")
            threading.Thread(
                target=self._process_audio,
                args=(audio_data,),
                daemon=True,
            ).start()
        except sd.PortAudioError as e:
            logger.exception(f"App: Failed to stop recording: {e}")
            self._event_queue.put(f"error:{e}")

    def _process_audio(self, audio_data) -> None:
        """Transcribe audio and output text (runs in background thread)."""
        logger.debug(f"App: Processing audio data ({len(audio_data)} samples)")
        if self._auto_stopped:
            logger.info("App: Auto-stopped recording; skipping transcription")
            self._event_queue.put("status:Ready (auto-stopped)")
            self._auto_stopped = False
            return

        # Check for empty buffer (likely stale stream after USB re-enumeration).
        # Delegate reinitialize to a dedicated thread via event queue; direct call
        # here would invoke Pa_Terminate() from the audio processing thread.
        if len(audio_data) == 0:
            logger.warning("App: Empty buffer detected, requesting audio stream reinitialize")
            self._event_queue.put("reinitialize")
            return

        # Check minimum duration
        if len(audio_data) < SAMPLE_RATE * MIN_RECORDING_SECONDS:
            logger.info("App: Recording too short, skipping")
            self._event_queue.put("status:Ready (too short)")
            return

        # Check if audio is too quiet (likely no speech)
        rms = np.sqrt(np.mean(audio_data.astype(np.float64) ** 2))
        logger.debug(f"App: RMS={rms:.2f}, threshold={self._rms_threshold}")
        if self._debug:
            print(f"[DEBUG] RMS: {rms:.2f} (threshold: {self._rms_threshold})")
        if rms < self._rms_threshold:
            logger.info("App: Audio too quiet, skipping")
            self._event_queue.put("status:Ready (no audio)")
            return

        audio_path = None
        try:
            logger.debug("App: Saving audio to file")
            audio_path = save_audio(audio_data)

            logger.info("App: Starting transcription")
            text = transcribe(audio_path)
            logger.info(f"App: Transcription complete ({len(text)} chars)")

            if text and text.strip():
                logger.debug("App: Outputting text")
                output_text(text)
                self._event_queue.put("status:Ready")
                logger.info("App: Processing complete")
            else:
                logger.info("App: No speech detected in transcription")
                self._event_queue.put("status:Ready (no speech)")

        except (OSError, ValueError, openai.OpenAIError) as e:
            logger.exception(f"App: Error during audio processing: {e}")
            self._event_queue.put(f"error:{e}")
        finally:
            if audio_path is not None:
                audio_path.unlink(missing_ok=True)
                logger.debug("App: Temporary audio file deleted")

    def _cleanup(self) -> None:
        """Clean up resources on app termination."""
        logger.info("App: Cleanup triggered")
        if self._device_monitor is not None:
            self._device_monitor.stop()
        self.hotkey_listener.stop()
        self.recorder.cleanup()
        logger.info("App: Cleanup complete")

    def run(self) -> None:
        """Start the app and hotkey listener."""
        logger.info("App: Starting Voice Input application")
        logger.info(
            f"App: Hotkey={self._current_hotkey}, Mode={self._current_mode}, "
            f"RMS threshold={self._rms_threshold}"
        )

        # Resolve configured input device (name -> index)
        device_index = self._resolve_input_device_index(self._current_input_device_name)
        if self._current_input_device_name is not None and device_index is None:
            logger.warning("App: Configured input device not found; using OS default")
            self._current_input_device_name = None
            self._config["input_device"] = None
            save_config(self._config)
            self._populate_input_device_menu()
        self.recorder.set_device(device_index)

        # Initialize audio stream
        try:
            self.recorder.initialize()
        except (RuntimeError, sd.PortAudioError) as e:
            logger.exception(f"App: Failed to initialize audio stream: {e}")
            rumps.notification(
                title="Voice Input Error",
                subtitle="Failed to start",
                message=f"Audio initialization failed: {e}",
            )
            return

        # Register cleanup handler
        atexit.register(self._cleanup)

        # Start device monitor (sleep/wake and audio device hot-plug)
        self._device_monitor = DeviceMonitor(
            on_sleep=self._on_system_sleep,
            on_wake=self._on_system_wake,
            on_device_change=self._on_audio_device_change,
        )
        self._device_monitor.start()

        self.hotkey_listener.start()
        super().run()


def main() -> None:
    """Entry point for menu bar app."""
    import argparse
    import logging
    import os

    from dotenv import load_dotenv

    from .logger import set_console_log_level

    parser = argparse.ArgumentParser(description="Voice Input - Mac menu bar app")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()

    if args.debug:
        set_console_log_level(logging.DEBUG)

    load_dotenv()

    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is not set")
        print("Please create a .env file with your API key")
        return

    if not check_accessibility_permission(prompt=True):
        print("Error: アクセシビリティ権限が必要です")
        print("システム設定 > プライバシーとセキュリティ > アクセシビリティ")
        print("で Voice Input を許可してください")
        return

    app = VoiceInputApp(debug=args.debug)
    app.run()


if __name__ == "__main__":
    main()
