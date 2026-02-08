"""Tests for accessibility module."""

from unittest.mock import MagicMock, patch

from voice_input.accessibility import check_accessibility_permission


class TestCheckAccessibilityPermission:
    """Tests for check_accessibility_permission function."""

    def test_returns_true_when_permission_granted(self):
        """Test that True is returned when accessibility is granted."""
        with patch("voice_input.accessibility.ctypes") as mock_ctypes:
            # Set up mock library loading
            mock_ctypes.util.find_library.side_effect = lambda name: f"/path/to/{name}"

            mock_cf = MagicMock()
            mock_hi = MagicMock()
            mock_ctypes.cdll.LoadLibrary.side_effect = [mock_cf, mock_hi]

            # Mock kCFBooleanTrue
            mock_ctypes.c_void_p.in_dll.return_value = MagicMock()

            # Mock AXIsProcessTrustedWithOptions to return True
            mock_hi.AXIsProcessTrustedWithOptions.return_value = True

            result = check_accessibility_permission(prompt=True)

            assert result is True

    def test_returns_false_when_permission_denied(self):
        """Test that False is returned when accessibility is denied."""
        with patch("voice_input.accessibility.ctypes") as mock_ctypes:
            # Set up mock library loading
            mock_ctypes.util.find_library.side_effect = lambda name: f"/path/to/{name}"

            mock_cf = MagicMock()
            mock_hi = MagicMock()
            mock_ctypes.cdll.LoadLibrary.side_effect = [mock_cf, mock_hi]

            # Mock kCFBooleanTrue
            mock_ctypes.c_void_p.in_dll.return_value = MagicMock()

            # Mock AXIsProcessTrustedWithOptions to return False
            mock_hi.AXIsProcessTrustedWithOptions.return_value = False

            result = check_accessibility_permission(prompt=True)

            assert result is False

    def test_returns_true_when_corefouncation_not_found(self):
        """Test fallback when CoreFoundation is not found (non-macOS)."""
        with patch("voice_input.accessibility.ctypes") as mock_ctypes:
            # CoreFoundation not found
            mock_ctypes.util.find_library.return_value = None

            result = check_accessibility_permission()

            assert result is True

    def test_returns_true_when_hiservices_not_found(self):
        """Test fallback when HIServices is not found."""
        with patch("voice_input.accessibility.ctypes") as mock_ctypes:
            # CoreFoundation found, but HIServices not found
            def find_library(name: str):
                if name == "CoreFoundation":
                    return "/path/to/CoreFoundation"
                return None

            mock_ctypes.util.find_library.side_effect = find_library
            mock_ctypes.cdll.LoadLibrary.return_value = MagicMock()

            result = check_accessibility_permission()

            assert result is True

    def test_returns_true_on_oserror(self):
        """Test that OSError is caught and True is returned."""
        with patch("voice_input.accessibility.ctypes") as mock_ctypes:
            mock_ctypes.util.find_library.side_effect = OSError("Library not found")

            result = check_accessibility_permission()

            assert result is True

    def test_prompt_false_does_not_show_dialog(self):
        """Test that prompt=False creates no options dictionary."""
        with patch("voice_input.accessibility.ctypes") as mock_ctypes:
            mock_ctypes.util.find_library.side_effect = lambda name: f"/path/to/{name}"

            mock_cf = MagicMock()
            mock_hi = MagicMock()
            mock_ctypes.cdll.LoadLibrary.side_effect = [mock_cf, mock_hi]

            mock_ctypes.c_void_p.in_dll.return_value = MagicMock()
            mock_hi.AXIsProcessTrustedWithOptions.return_value = True

            check_accessibility_permission(prompt=False)

            # AXIsProcessTrustedWithOptions should be called with None
            mock_hi.AXIsProcessTrustedWithOptions.assert_called_once_with(None)
