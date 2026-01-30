"""Tests for hotkey module."""

from unittest.mock import Mock

from pynput import keyboard

from voice_input.hotkey import HotkeyListener


class TestHotkeyListenerHoldMode:
    """Tests for hold-to-record mode (existing behavior).

    Note:
        Uses Mock for callbacks because HotkeyListener only calls
        callbacks without return values, making Mock the simplest
        way to verify calls without side effects.
    """

    def test_press_triggers_on_press_callback(self):
        # Arrange
        on_press = Mock()
        on_release = Mock()
        listener = HotkeyListener(
            on_press=on_press,
            on_release=on_release,
            hotkey="ctrl_l",
        )

        # Act
        listener._handle_press(keyboard.Key.ctrl_l)

        # Assert
        on_press.assert_called_once()
        on_release.assert_not_called()
