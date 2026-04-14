"""Accessibility permission check for macOS (pyobjc-backed)."""

import sys

from .logger import get_logger

logger = get_logger()


def check_accessibility_permission(prompt: bool = True) -> bool:
    """Check if the application has accessibility permission on macOS.

    Uses pyobjc (ApplicationServices) instead of raw ctypes. The previous
    ctypes implementation segfaulted inside ``AXIsProcessTrustedWithOptions``
    in PyInstaller bundles because ``CFDictionaryCreate`` silently returned
    NULL when pointers to ``kCFBooleanTrue`` did not resolve across
    framework instances.

    Args:
        prompt: If True, show the system dialog to request permission
            when not granted.

    Returns:
        True if permission is granted; False if denied or if the check
        itself failed. On non-macOS platforms the check is skipped and
        True is returned so the app can start up at all.
    """
    # On non-macOS we skip the permission check so the app can start for
    # development/test purposes. The rest of the app obviously won't work,
    # but that surfaces as a different error, not a false negative here.
    if sys.platform != "darwin":
        return True

    try:
        from ApplicationServices import (
            AXIsProcessTrustedWithOptions,
            kAXTrustedCheckOptionPrompt,
        )
    except ImportError as exc:
        # On macOS this means pyobjc failed to load (missing install, broken
        # bundle, etc.). Don't silently claim trust — the user would only
        # notice later when paste stops working. Return False and log loudly.
        logger.warning(
            "Accessibility check unavailable — failed to import "
            f"ApplicationServices: {exc}"
        )
        return False

    options = {kAXTrustedCheckOptionPrompt: True} if prompt else None
    try:
        return bool(AXIsProcessTrustedWithOptions(options))
    except Exception as exc:  # noqa: BLE001 - defensive: framework-level failure
        logger.warning(f"Accessibility check raised: {exc}")
        return False
