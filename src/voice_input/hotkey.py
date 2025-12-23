"""Global hotkey listener using pynput."""

from collections.abc import Callable

from pynput import keyboard


class HotkeyListener:
    """Global hotkey listener for Left Option key (hold-to-record).

    Detects when the Left Option key is pressed and released,
    triggering callbacks for each event.
    """

    def __init__(
        self,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
    ) -> None:
        """Initialize the hotkey listener.

        Args:
            on_press: Callback when Left Option key is pressed.
            on_release: Callback when Left Option key is released.
        """
        self._on_press = on_press
        self._on_release = on_release
        self._listener: keyboard.Listener | None = None
        self._is_pressed = False  # Debounce flag

    def _handle_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        """Handle key press events."""
        if key == keyboard.Key.alt_l and not self._is_pressed:
            self._is_pressed = True
            self._on_press()

    def _handle_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        """Handle key release events."""
        if key == keyboard.Key.alt_l and self._is_pressed:
            self._is_pressed = False
            self._on_release()

    def start(self) -> None:
        """Start listening for hotkey events."""
        self._listener = keyboard.Listener(
            on_press=self._handle_press,
            on_release=self._handle_release,
        )
        self._listener.start()

    def stop(self) -> None:
        """Stop listening for hotkey events."""
        if self._listener:
            self._listener.stop()
            self._listener = None

    @property
    def is_pressed(self) -> bool:
        """Return whether the hotkey is currently pressed."""
        return self._is_pressed
