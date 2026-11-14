"""Text output module for clipboard and paste."""

import time

import pyperclip

from .logger import get_logger

logger = get_logger()

V_KEY = 0x09
RETURN_KEY = 0x24


def copy_to_clipboard(text: str) -> None:
    """Copy text to clipboard.

    Args:
        text: Text to copy.
    """
    pyperclip.copy(text)
    logger.debug("Copied text to clipboard (%d characters)", len(text))


def _post_key(keycode: int, *, command: bool = False) -> None:
    import Quartz

    if not Quartz.CGPreflightPostEventAccess():
        raise PermissionError("Keyboard output requires Accessibility permission")

    flags = Quartz.kCGEventFlagMaskCommand if command else 0
    for down in (True, False):
        event = Quartz.CGEventCreateKeyboardEvent(None, keycode, down)
        # Put Cmd on the V event itself: separate modifier events used to
        # produce a bare "v" with the hotkey listener running (issue #3).
        Quartz.CGEventSetFlags(event, flags)
        Quartz.CGEventPost(Quartz.kCGSessionEventTap, event)


def paste() -> None:
    time.sleep(0.1)
    _post_key(V_KEY, command=True)


# Delay after Cmd+V before restoring clipboard. macOS needs time to actually
# read the clipboard via the paste event; restore too early and the paste
# sees the restored (wrong) content.
CLIPBOARD_RESTORE_DELAY = 0.2


def press_enter() -> None:
    _post_key(RETURN_KEY)


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
