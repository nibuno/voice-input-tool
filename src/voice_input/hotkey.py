"""Global hotkey listener using pynput."""

from collections.abc import Callable

from pynput import keyboard

# Mapping from config string to pynput key
HOTKEY_MAP = {
    "ctrl_l": keyboard.Key.ctrl_l,
    "ctrl_r": keyboard.Key.ctrl_r,
    "alt_l": keyboard.Key.alt_l,
    "alt_r": keyboard.Key.alt_r,
}

# Display names for menu
HOTKEY_NAMES = {
    "ctrl_l": "Left Control",
    "ctrl_r": "Right Control",
    "alt_l": "Left Option",
    "alt_r": "Right Option",
}


class HotkeyListener:
    """Global hotkey listener (hold-to-record).

    Detects when the configured hotkey is pressed and released,
    triggering callbacks for each event.
    """

    def __init__(
        self,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
        hotkey: str = "ctrl_l",
    ) -> None:
        """Initialize the hotkey listener.

        Args:
            on_press: Callback when hotkey is pressed.
            on_release: Callback when hotkey is released.
            hotkey: Hotkey identifier (ctrl_l, ctrl_r, alt_l, alt_r).
        """
        self._on_press = on_press
        self._on_release = on_release
        self._hotkey = HOTKEY_MAP.get(hotkey, keyboard.Key.ctrl_l)
        self._listener: keyboard.Listener | None = None
        self._is_pressed = False  # Debounce flag

    def set_hotkey(self, hotkey: str) -> None:
        """Change the hotkey.

        Args:
            hotkey: Hotkey identifier (ctrl_l, ctrl_r, alt_l, alt_r).
        """
        self._hotkey = HOTKEY_MAP.get(hotkey, keyboard.Key.ctrl_l)
        # Reset pressed state when changing hotkey
        self._is_pressed = False

    def _handle_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        """Handle key press events."""
        if key == self._hotkey and not self._is_pressed:
            self._is_pressed = True
            self._on_press()

    def _handle_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        """Handle key release events."""
        if key == self._hotkey and self._is_pressed:
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
