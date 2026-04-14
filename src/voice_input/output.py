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


# Delay after Cmd+V before restoring clipboard. macOS needs time to actually
# read the clipboard via the paste event; restore too early and the paste
# sees the restored (wrong) content.
CLIPBOARD_RESTORE_DELAY = 0.2


def press_enter() -> None:
    """Simulate the Return key via AppleScript.

    Uses AppleScript for the same reason as paste(): pynput/pyautogui
    interfere when the hotkey listener is active.
    """
    try:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to keystroke return',
            ],
            capture_output=True,
            text=True,
            timeout=PASTE_TIMEOUT,
        )
        if result.returncode != 0:
            logger.warning(f"osascript (enter) failed: {result.stderr}")
        else:
            logger.debug("Return sent via AppleScript")
    except subprocess.TimeoutExpired:
        logger.warning(f"osascript (enter) timed out after {PASTE_TIMEOUT}s")
    except Exception as e:  # noqa: BLE001 - defensive, osascript is external
        logger.exception(f"Failed to press Enter: {e}")


def output_text(text: str, *, mode: str = "copy_paste") -> None:
    """Deliver transcribed text to the active application.

    Args:
        text: Text to output.
        mode: ``copy_paste`` (default) keeps text on the clipboard after pasting.
            ``paste_enter`` preserves the user's pre-existing clipboard content
            by restoring it after the paste, and presses Enter afterwards.
    """
    if mode == "paste_enter":
        original = pyperclip.paste()
        copy_to_clipboard(text)
        paste()
        # Wait for the paste target to consume the clipboard before restoring.
        time.sleep(CLIPBOARD_RESTORE_DELAY)
        try:
            pyperclip.copy(original)
            logger.debug("Clipboard restored to pre-transcription content")
        except Exception as e:  # noqa: BLE001 - pyperclip errors are opaque
            logger.warning(f"Failed to restore clipboard: {e}")
        press_enter()
        return

    # Default: copy_paste
    copy_to_clipboard(text)
    paste()
