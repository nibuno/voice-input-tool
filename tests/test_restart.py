"""Tests for the self-restart helper."""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import voice_input.restart as restart


@pytest.fixture
def throttle_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the throttle file to a tmp path for the duration of the test."""
    path = tmp_path / ".voice-input" / ".last_restart"
    monkeypatch.setattr(restart, "_THROTTLE_FILE", path)
    return path


@pytest.fixture
def patched_exits(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Intercept process-terminating calls so tests can assert them safely."""
    calls: dict = {"popen": None, "execv": None, "exit": None, "notify": None}

    def fake_popen(args):
        calls["popen"] = args
        return MagicMock()

    def fake_execv(path, argv):
        calls["execv"] = (path, argv)

    def fake_exit(code):
        calls["exit"] = code
        # os._exit never returns; mimic that so callers don't continue into
        # the execv fallback (which would otherwise record a spurious call).
        raise SystemExit(code)

    def fake_notify(message):
        calls["notify"] = message

    monkeypatch.setattr(restart.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(restart.os, "execv", fake_execv)
    monkeypatch.setattr(restart.os, "_exit", fake_exit)
    monkeypatch.setattr(restart, "_notify_user_sync", fake_notify)
    return calls


def test_throttled_returns_false_when_file_missing(throttle_file: Path) -> None:
    assert not throttle_file.exists()
    assert restart._throttled() is False


def test_throttled_true_inside_window(throttle_file: Path) -> None:
    throttle_file.parent.mkdir(parents=True, exist_ok=True)
    throttle_file.write_text(str(time.time() - 5))  # 5s ago
    assert restart._throttled() is True


def test_throttled_false_outside_window(throttle_file: Path) -> None:
    throttle_file.parent.mkdir(parents=True, exist_ok=True)
    throttle_file.write_text(str(time.time() - (restart._MIN_RESTART_INTERVAL + 10)))
    assert restart._throttled() is False


def test_throttled_suppresses_on_corrupted_file(throttle_file: Path) -> None:
    """Unreadable state should pessimistically block the restart."""
    throttle_file.parent.mkdir(parents=True, exist_ok=True)
    throttle_file.write_text("not-a-float")
    assert restart._throttled() is True


def test_schedule_self_restart_aborts_when_throttled(
    throttle_file: Path,
    patched_exits: dict,
) -> None:
    throttle_file.parent.mkdir(parents=True, exist_ok=True)
    throttle_file.write_text(str(time.time()))  # now

    assert restart.schedule_self_restart("test") is False
    assert patched_exits["popen"] is None
    assert patched_exits["execv"] is None
    assert patched_exits["exit"] is None


def test_schedule_self_restart_dev_mode_uses_execv(
    throttle_file: Path,
    patched_exits: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without sys.frozen and .app we fall through to os.execv."""
    monkeypatch.delattr(sys, "frozen", raising=False)

    restart.schedule_self_restart("dev reason")

    assert patched_exits["execv"] is not None
    path, argv = patched_exits["execv"]
    assert path == sys.executable
    assert argv[0] == sys.executable
    # Did not try the bundle path.
    assert patched_exits["popen"] is None
    # Did not call os._exit in dev mode (execv replaces the process).
    assert patched_exits["exit"] is None


def test_schedule_self_restart_bundle_mode_uses_open(
    throttle_file: Path,
    patched_exits: dict,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inside a .app bundle we invoke `open -n <bundle>` and os._exit(0)."""
    bundle = tmp_path / "VoiceInput.app"
    bundle_exe = bundle / "Contents" / "MacOS" / "VoiceInput"
    bundle_exe.parent.mkdir(parents=True)
    bundle_exe.touch()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(bundle_exe))

    with pytest.raises(SystemExit):
        restart.schedule_self_restart("frozen reason")

    assert patched_exits["popen"] is not None
    assert patched_exits["popen"][0] == "open"
    assert patched_exits["popen"][1] == "-n"
    assert patched_exits["popen"][2] == str(bundle)
    assert patched_exits["exit"] == 0
    # Dev-mode execv must NOT run when we took the bundle path.
    assert patched_exits["execv"] is None


def test_schedule_self_restart_falls_back_when_bundle_not_app(
    throttle_file: Path,
    patched_exits: dict,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A frozen build whose parent isn't `.app` (onefile etc.) falls back to execv."""
    exe = tmp_path / "random" / "bin" / "VoiceInput"
    exe.parent.mkdir(parents=True)
    exe.touch()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))

    restart.schedule_self_restart("onefile reason")

    # Bundle path not taken.
    assert patched_exits["popen"] is None
    assert patched_exits["exit"] is None
    # execv path taken instead.
    assert patched_exits["execv"] is not None


def test_schedule_self_restart_emits_user_notification(
    throttle_file: Path,
    patched_exits: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    restart.schedule_self_restart("notify")
    assert patched_exits["notify"] is not None
