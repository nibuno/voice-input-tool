"""Self-restart helper for recovering from unrecoverable PortAudio state."""

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from .logger import get_logger

logger = get_logger()

# Throttle file: prevents restart loops by recording the last restart timestamp.
_THROTTLE_FILE = Path.home() / ".voice-input" / ".last_restart"

# Minimum seconds between self-restarts. A crash loop is more visible than
# helpful, so refuse to restart if we already restarted this recently.
_MIN_RESTART_INTERVAL = 60.0


def _throttled() -> bool:
    """Return True if a recent restart happened within the throttle window.

    On any read failure we pessimistically return True (= suppress restart),
    so a corrupted state file doesn't accidentally enable a crash loop.
    """
    try:
        if not _THROTTLE_FILE.exists():
            return False
        last = float(_THROTTLE_FILE.read_text().strip())
    except (OSError, ValueError) as exc:
        logger.warning(
            f"Restart: throttle file unreadable ({exc}); suppressing restart"
        )
        return True
    return (time.time() - last) < _MIN_RESTART_INTERVAL


def _record_restart() -> None:
    try:
        _THROTTLE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _THROTTLE_FILE.write_text(str(time.time()))
    except OSError as exc:
        logger.warning(f"Restart: failed to record throttle file: {exc}")


def _resolve_bundle_path() -> Path | None:
    """Return the enclosing ``.app`` bundle path, or None if unrecognisable.

    Assumes the standard PyInstaller onedir + BUNDLE layout:
    ``VoiceInput.app/Contents/MacOS/VoiceInput``.
    """
    exe = Path(sys.executable).resolve()
    if len(exe.parents) < 3:
        return None
    candidate = exe.parents[2]
    if candidate.suffix != ".app" or not candidate.exists():
        return None
    return candidate


def _notify_user_sync(message: str) -> None:
    """Block until a macOS notification has been dispatched.

    ``rumps.notification`` queues through this process's run loop, which is
    about to die; use ``osascript`` synchronously so the banner actually
    surfaces before we exit.
    """
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification "{message}" with title "Voice Input"',
            ],
            check=False,
            timeout=2.0,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning(f"Restart: notify failed: {exc}")


def schedule_self_restart(reason: str) -> bool:
    """Relaunch this process, then terminate.

    Returns:
        True if a restart was launched; False if throttled (caller should
        continue without restarting).
    """
    if _throttled():
        logger.warning(
            f"Restart: suppressed (< {_MIN_RESTART_INTERVAL}s since last restart). "
            f"Reason: {reason}"
        )
        return False

    _record_restart()
    logger.warning(f"Restart: self-restart initiated. Reason: {reason}")
    _notify_user_sync("音声ストリームを復旧できなかったため再起動します")

    bundle = _resolve_bundle_path() if getattr(sys, "frozen", False) else None
    if bundle is not None:
        try:
            subprocess.Popen(["open", "-n", str(bundle)])
        except OSError as exc:
            logger.exception(f"Restart: failed to launch bundle: {exc}")
            return False
        # Flush handlers before hard-exit — os._exit skips atexit/shutdown.
        logging.shutdown()
        os._exit(0)

    # Dev mode (or frozen build without a recognisable .app bundle): replace
    # this process in place. ``os.execv`` also bypasses atexit, but the
    # replacement image re-initialises logging on start.
    logging.shutdown()
    try:
        os.execv(sys.executable, [sys.executable, *sys.argv])
    except OSError as exc:
        logger.exception(f"Restart: execv failed: {exc}")
        return False
    return True  # unreachable
