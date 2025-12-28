"""Mac menu bar application for voice input."""

import queue
import threading

import numpy as np
import rumps

from .config import load_config, save_config
from .hotkey import HOTKEY_NAMES, HotkeyListener
from .output import output_text
from .recorder import SAMPLE_RATE, StreamingRecorder, save_audio
from .transcriber import transcribe

# Minimum recording duration in seconds
MIN_RECORDING_SECONDS = 0.3

# Minimum RMS (root mean square) amplitude to consider as speech
# int16 audio ranges from -32768 to 32767
# This threshold filters out silence and very quiet recordings
MIN_RMS_THRESHOLD = 100


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
        self._rms_threshold = self._config.get("rms_threshold", MIN_RMS_THRESHOLD)

        self.recorder = StreamingRecorder()
        self._event_queue: queue.Queue[str] = queue.Queue()

        self.hotkey_listener = HotkeyListener(
            on_press=lambda: self._event_queue.put("start"),
            on_release=lambda: self._event_queue.put("stop"),
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

        self.menu = [
            self.status_item,
            None,  # Separator
            self.hotkey_menu,
            rumps.MenuItem("Language: Japanese"),
        ]

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

    @rumps.timer(0.05)
    def _check_events(self, _sender: object) -> None:
        """Poll for hotkey events from the queue."""
        try:
            while True:
                event = self._event_queue.get_nowait()
                if event == "start":
                    self._start_recording()
                elif event == "stop":
                    self._stop_recording()
                elif event.startswith("status:"):
                    status = event[7:]
                    self.title = "Voice Input"
                    self.status_item.title = f"Status: {status}"
                elif event.startswith("error:"):
                    message = event[6:]
                    self.title = "Voice Input"
                    self.status_item.title = "Status: Error"
                    rumps.notification(
                        title="Voice Input Error",
                        subtitle="",
                        message=message,
                    )
        except queue.Empty:
            pass

    def _start_recording(self) -> None:
        """Start recording audio."""
        self.title = "Recording..."
        self.status_item.title = "Status: Recording..."
        self.recorder.start()

    def _stop_recording(self) -> None:
        """Stop recording and process audio."""
        audio_data = self.recorder.stop()
        self.title = "Processing..."
        self.status_item.title = "Status: Processing..."

        # Process in background thread
        threading.Thread(
            target=self._process_audio,
            args=(audio_data,),
            daemon=True,
        ).start()

    def _process_audio(self, audio_data) -> None:
        """Transcribe audio and output text (runs in background thread)."""
        # Check minimum duration
        if len(audio_data) < SAMPLE_RATE * MIN_RECORDING_SECONDS:
            self._event_queue.put("status:Ready (too short)")
            return

        # Check if audio is too quiet (likely no speech)
        rms = np.sqrt(np.mean(audio_data.astype(np.float64) ** 2))
        if self._debug:
            print(f"[DEBUG] RMS: {rms:.2f} (threshold: {self._rms_threshold})")
        if rms < self._rms_threshold:
            self._event_queue.put("status:Ready (no audio)")
            return

        try:
            audio_path = save_audio(audio_data)
            text = transcribe(audio_path)
            audio_path.unlink(missing_ok=True)

            if text and text.strip():
                output_text(text)
                self._event_queue.put("status:Ready")
            else:
                self._event_queue.put("status:Ready (no speech)")

        except Exception as e:
            self._event_queue.put(f"error:{e}")

    def run(self) -> None:
        """Start the app and hotkey listener."""
        self.hotkey_listener.start()
        super().run()


def main() -> None:
    """Entry point for menu bar app."""
    import argparse
    import os

    from dotenv import load_dotenv

    parser = argparse.ArgumentParser(description="Voice Input - Mac menu bar app")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()

    load_dotenv()

    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is not set")
        print("Please create a .env file with your API key")
        return

    app = VoiceInputApp(debug=args.debug)
    app.run()


if __name__ == "__main__":
    main()
