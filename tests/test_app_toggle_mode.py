"""Tests for toggle mode logic.

These tests verify the toggle/hold mode behavior without depending on
the full VoiceInputApp class, which requires complex rumps mocking.
"""

from unittest.mock import Mock


class RecordingModeController:
    """Helper class that implements the mode logic for testing.

    This represents the logic that will be added to VoiceInputApp.
    """

    def __init__(self, mode: str = "hold"):
        self._mode = mode
        self._is_recording = False
        self.start_recording = Mock()
        self.stop_recording = Mock()

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self._is_recording = False

    def on_hotkey_press(self) -> None:
        if self._mode == "toggle":
            if self._is_recording:
                self._is_recording = False
                self.stop_recording()
            else:
                self._is_recording = True
                self.start_recording()
        else:  # hold mode
            self.start_recording()

    def on_hotkey_release(self) -> None:
        if self._mode == "hold":
            self.stop_recording()
        # toggle mode: release does nothing


class TestToggleMode:
    """Tests for toggle recording mode.

    In toggle mode:
    - First press starts recording
    - Second press stops recording
    - Key release does nothing
    """

    def test_first_press_starts_recording(self):
        """First press in toggle mode should start recording."""
        controller = RecordingModeController(mode="toggle")

        controller.on_hotkey_press()

        controller.start_recording.assert_called_once()
        controller.stop_recording.assert_not_called()

    def test_second_press_stops_recording(self):
        """Second press in toggle mode should stop recording."""
        controller = RecordingModeController(mode="toggle")

        controller.on_hotkey_press()  # start
        controller.on_hotkey_press()  # stop

        controller.start_recording.assert_called_once()
        controller.stop_recording.assert_called_once()

    def test_release_does_nothing(self):
        """Key release in toggle mode should not affect recording."""
        controller = RecordingModeController(mode="toggle")

        controller.on_hotkey_press()  # start
        controller.on_hotkey_release()  # should do nothing

        controller.start_recording.assert_called_once()
        controller.stop_recording.assert_not_called()

    def test_cycle(self):
        """Toggle mode should cycle: start -> stop -> start -> stop."""
        controller = RecordingModeController(mode="toggle")

        controller.on_hotkey_press()  # start
        controller.on_hotkey_press()  # stop
        controller.on_hotkey_press()  # start
        controller.on_hotkey_press()  # stop

        assert controller.start_recording.call_count == 2
        assert controller.stop_recording.call_count == 2


class TestHoldMode:
    """Tests for hold recording mode (existing behavior).

    In hold mode:
    - Press starts recording
    - Release stops recording
    """

    def test_press_starts_recording(self):
        """Press in hold mode should start recording."""
        controller = RecordingModeController(mode="hold")

        controller.on_hotkey_press()

        controller.start_recording.assert_called_once()
        controller.stop_recording.assert_not_called()

    def test_release_stops_recording(self):
        """Release in hold mode should stop recording."""
        controller = RecordingModeController(mode="hold")

        controller.on_hotkey_press()
        controller.on_hotkey_release()

        controller.start_recording.assert_called_once()
        controller.stop_recording.assert_called_once()

    def test_multiple_press_release_cycles(self):
        """Hold mode should support multiple press-release cycles."""
        controller = RecordingModeController(mode="hold")

        controller.on_hotkey_press()
        controller.on_hotkey_release()
        controller.on_hotkey_press()
        controller.on_hotkey_release()

        assert controller.start_recording.call_count == 2
        assert controller.stop_recording.call_count == 2


class TestModeSwitch:
    """Tests for switching between modes."""

    def test_switch_to_toggle_resets_recording_state(self):
        """Switching to toggle mode should reset recording state."""
        controller = RecordingModeController(mode="toggle")

        # Start recording
        controller.on_hotkey_press()
        assert controller._is_recording is True

        # Switch mode - should reset state
        controller.set_mode("toggle")
        assert controller._is_recording is False

        # Press should start (not stop)
        controller.on_hotkey_press()
        assert controller.start_recording.call_count == 2

    def test_switch_from_hold_to_toggle(self):
        """Switching from hold to toggle should work correctly."""
        controller = RecordingModeController(mode="hold")

        # Use hold mode
        controller.on_hotkey_press()
        controller.on_hotkey_release()

        # Switch to toggle
        controller.set_mode("toggle")

        # Use toggle mode
        controller.on_hotkey_press()  # start
        controller.on_hotkey_release()  # nothing
        controller.on_hotkey_press()  # stop

        assert controller.start_recording.call_count == 2
        assert controller.stop_recording.call_count == 2

    def test_default_mode_is_hold(self):
        """Default mode should be hold for backwards compatibility."""
        controller = RecordingModeController()

        assert controller._mode == "hold"
