"""Text output module for clipboard and paste."""

import time

import pyautogui
import pyperclip


def copy_to_clipboard(text: str) -> None:
    """Copy text to clipboard.

    Args:
        text: Text to copy.
    """
    pyperclip.copy(text)


def paste() -> None:
    """Simulate Cmd+V to paste from clipboard."""
    time.sleep(0.1)  # Small delay to ensure clipboard is ready
    pyautogui.hotkey("command", "v")


def output_text(text: str) -> None:
    """Copy text to clipboard and paste it.

    Args:
        text: Text to output.
    """
    copy_to_clipboard(text)
    paste()
