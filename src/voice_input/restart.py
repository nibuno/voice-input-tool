"""Self-restart helper for recovering from unrecoverable PortAudio state."""

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
    """Return True if a recent restart happened within the throttle window."""
    try:
        if not _THROTTLE_FILE.exists():
            return False
        last = float(_THROTTLE_FILE.read_text().strip())
    except (OSError, ValueError):
        return False
    return (time.time() - last) < _MIN_RESTART_INTERVAL


def _record_restart() -> None:
    try:
        _THROTTLE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _THROTTLE_FILE.write_text(str(time.time()))
    except OSError as exc:
        logger.warning(f"Restart: failed to record throttle file: {exc}")


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

    if getattr(sys, "frozen", False):
        # PyInstaller bundle: executable lives at
        # VoiceInput.app/Contents/MacOS/VoiceInput — walk up to the .app.
        exe = Path(sys.executable).resolve()
        bundle = exe.parents[2] if len(exe.parents) >= 3 else exe
        try:
            subprocess.Popen(["open", "-n", str(bundle)])
        except OSError as exc:
            logger.exception(f"Restart: failed to launch bundle: {exc}")
            return False
        # Exit this process so the fresh instance can take over.
        os._exit(0)

    # Dev mode: replace this process in-place.
    try:
        os.execv(sys.executable, [sys.executable, *sys.argv])
    except OSError as exc:
        logger.exception(f"Restart: execv failed: {exc}")
        return False
    return True  # unreachable
