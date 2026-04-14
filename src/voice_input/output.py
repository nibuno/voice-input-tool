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


def _clipboard_has_non_text_payload() -> bool:
    """Return True if the system clipboard holds image/file/RTF-only content.

    pyperclip can only round-trip plain text, so if the user's current
    clipboard is an image or a file reference the save/restore trick in
    ``paste_enter`` mode would silently erase it. Detect that case so we can
    skip the restore step and leave the data lost-but-acknowledged rather
    than silently.

    Only available on macOS with pyobjc (AppKit). On other platforms this
    returns False and the caller falls back to the plain-text path.
    """
    try:
        from AppKit import NSPasteboard
    except ImportError:
        return False
    pb = NSPasteboard.generalPasteboard()
    types = list(pb.types() or [])
    if not types:
        return False
    # Text-bearing UTIs we can safely round-trip through pyperclip.
    text_utis = {
        "public.utf8-plain-text",
        "public.plain-text",
        "public.utf16-plain-text",
        "NSStringPboardType",
    }
    return not any(t in text_utis for t in types)


def output_text(text: str, *, mode: str = "copy_paste") -> None:
    """Deliver transcribed text to the active application.

    Args:
        text: Text to output.
        mode: ``copy_paste`` (default) keeps text on the clipboard after
            pasting. ``paste_enter`` preserves the user's pre-existing
            *text* clipboard content by restoring it after the paste, and
            then presses Enter to auto-submit. If the clipboard holds
            non-text data (image/file) the restore is skipped — pyperclip
            would clobber it anyway — and a warning is logged.
    """
    if mode == "paste_enter":
        non_text = _clipboard_has_non_text_payload()
        if non_text:
            logger.warning(
                "Clipboard holds non-text data; it will be lost by paste_enter"
            )
            original = None
        else:
            original = pyperclip.paste()

        paste_ok = False
        try:
            copy_to_clipboard(text)
            paste()
            # Wait for the paste target to consume the clipboard before restoring.
            time.sleep(CLIPBOARD_RESTORE_DELAY)
            paste_ok = True
        finally:
            # Restore in a finally block so an exception during paste still
            # returns the user's clipboard. Only restore if we captured text
            # (skipping for non-text clipboards avoids clobbering images).
            if original is not None:
                try:
                    pyperclip.copy(original)
                    logger.debug("Clipboard restored to pre-transcription content")
                except Exception as e:  # noqa: BLE001 - pyperclip errors are opaque
                    logger.warning(f"Failed to restore clipboard: {e}")
        # Only auto-submit when the paste actually succeeded. A failed paste
        # means the target app never got the text, so pressing Enter would
        # submit whatever stale input is already in the field.
        if paste_ok:
            press_enter()
        return

    # Default: copy_paste
    copy_to_clipboard(text)
    paste()
