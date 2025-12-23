"""Mac menu bar application for voice input."""

import queue
import threading

import rumps

from .hotkey import HotkeyListener
from .output import output_text
from .recorder import SAMPLE_RATE, StreamingRecorder, save_audio
from .transcriber import transcribe

# Minimum recording duration in seconds
MIN_RECORDING_SECONDS = 0.3


class VoiceInputApp(rumps.App):
    """Mac menu bar application for voice input using Whisper API."""

    def __init__(self) -> None:
        super().__init__(
            name="Voice Input",
            title="Voice Input",
        )

        self.recorder = StreamingRecorder()
        self._event_queue: queue.Queue[str] = queue.Queue()

        self.hotkey_listener = HotkeyListener(
            on_press=lambda: self._event_queue.put("start"),
            on_release=lambda: self._event_queue.put("stop"),
        )

        # Menu items
        self.status_item = rumps.MenuItem("Status: Ready")
        self.menu = [
            self.status_item,
            None,  # Separator
            rumps.MenuItem("Hotkey: Left Option (hold)"),
            rumps.MenuItem("Language: Japanese"),
        ]

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
    import os

    from dotenv import load_dotenv

    load_dotenv()

    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is not set")
        print("Please create a .env file with your API key")
        return

    app = VoiceInputApp()
    app.run()


if __name__ == "__main__":
    main()
