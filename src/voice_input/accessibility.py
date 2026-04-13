"""Accessibility permission check for macOS (pyobjc-backed)."""

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
        True if permission is granted (or we're not on macOS); False otherwise.
    """
    try:
        from ApplicationServices import (
            AXIsProcessTrustedWithOptions,
            kAXTrustedCheckOptionPrompt,
        )
    except ImportError:
        # Not on macOS, or pyobjc not available — assume OK.
        return True

    options = {kAXTrustedCheckOptionPrompt: True} if prompt else None
    try:
        return bool(AXIsProcessTrustedWithOptions(options))
    except Exception as exc:  # noqa: BLE001 - defensive: framework-level failure
        logger.warning(f"Accessibility check raised: {exc}")
        return False
