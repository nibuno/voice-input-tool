"""Text output module for clipboard and paste."""

import subprocess
import time

import pyperclip

from .logger import get_logger

logger = get_logger()

PASTE_TIMEOUT = 5.0  # Timeout for osascript in seconds


def copy_to_clipboard(text: str) -> None:
    """Copy text to clipboard.

    Args:
        text: Text to copy.
    """
    pyperclip.copy(text)
    logger.debug(f"Copied to clipboard: {text[:50]}...")


def paste() -> None:
    """Simulate Cmd+V using AppleScript.

    Why AppleScript instead of pyautogui:
    - pyautogui and pynput both use macOS Quartz API
    - When pynput keyboard listener is active, pyautogui.hotkey("command", "v")
      results in only "v" being typed (Cmd key is ignored)
    - AppleScript runs in a separate process (osascript), avoiding this interference

    See Issue #3 for details.
    """
    # Verify clipboard content before paste
    clipboard_content = pyperclip.paste()
    logger.debug(f"Clipboard before paste: {clipboard_content[:50]}...")

    time.sleep(0.1)  # Small delay before paste
    logger.debug("Sending Cmd+V via AppleScript")

    try:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to keystroke "v" using command down',
            ],
            capture_output=True,
            text=True,
            timeout=PASTE_TIMEOUT,
        )
        if result.returncode != 0:
            logger.warning(f"osascript failed: {result.stderr}")
        else:
            logger.debug("Cmd+V sent via AppleScript")
    except subprocess.TimeoutExpired:
        logger.warning(f"osascript timed out after {PASTE_TIMEOUT}s")
    except Exception as e:
        logger.exception(f"Failed to paste: {e}")


def output_text(text: str) -> None:
    """Copy text to clipboard and paste it.

    Args:
        text: Text to output.
    """
    copy_to_clipboard(text)
    paste()
