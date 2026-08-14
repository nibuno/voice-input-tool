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

    def test_release_triggers_on_release_callback(self):
        # Arrange
        on_press = Mock()
        on_release = Mock()
        listener = HotkeyListener(
            on_press=on_press,
            on_release=on_release,
            hotkey="ctrl_l",
        )
        listener._handle_press(keyboard.Key.ctrl_l)

        # Act
        listener._handle_release(keyboard.Key.ctrl_l)

        # Assert
        on_release.assert_called_once()

    def test_press_is_debounced(self):
        # Arrange
        on_press = Mock()
        listener = HotkeyListener(
            on_press=on_press,
            on_release=Mock(),
            hotkey="ctrl_l",
        )

        # Act - simulate OS key repeat
        listener._handle_press(keyboard.Key.ctrl_l)
        listener._handle_press(keyboard.Key.ctrl_l)
        listener._handle_press(keyboard.Key.ctrl_l)

        # Assert - only triggered once
        on_press.assert_called_once()

    def test_release_without_press_does_nothing(self):
        # Arrange
        on_release = Mock()
        listener = HotkeyListener(
            on_press=Mock(),
            on_release=on_release,
            hotkey="ctrl_l",
        )

        # Act - release without prior press
        listener._handle_release(keyboard.Key.ctrl_l)

        # Assert
        on_release.assert_not_called()

    def test_ignores_different_key(self):
        # Arrange
        on_press = Mock()
        on_release = Mock()
        listener = HotkeyListener(
            on_press=on_press,
            on_release=on_release,
            hotkey="ctrl_l",
        )

        # Act - press different key
        listener._handle_press(keyboard.Key.ctrl_r)
        listener._handle_release(keyboard.Key.ctrl_r)

        # Assert
        on_press.assert_not_called()
        on_release.assert_not_called()

    def test_set_hotkey_resets_pressed_state(self):
        # Arrange
        on_release = Mock()
        listener = HotkeyListener(
            on_press=Mock(),
            on_release=on_release,
            hotkey="ctrl_l",
        )
        listener._handle_press(keyboard.Key.ctrl_l)

        # Act
        listener.set_hotkey("ctrl_r")

        # Assert - state is reset, release on old key does nothing
        listener._handle_release(keyboard.Key.ctrl_l)
        on_release.assert_not_called()

    def test_escape_triggers_cancel_callback(self):
        on_cancel = Mock()
        listener = HotkeyListener(
            on_press=Mock(),
            on_release=Mock(),
            on_cancel=on_cancel,
            hotkey="ctrl_l",
        )

        listener._handle_press(keyboard.Key.esc)

        on_cancel.assert_called_once()

    def test_escape_does_not_trigger_recording_hotkey(self):
        on_press = Mock()
        listener = HotkeyListener(
            on_press=on_press,
            on_release=Mock(),
            on_cancel=Mock(),
            hotkey="ctrl_l",
        )

        listener._handle_press(keyboard.Key.esc)

        on_press.assert_not_called()
