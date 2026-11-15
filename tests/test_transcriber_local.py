"""The API edition shells out to the local edition; failures must stay visible."""

import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from voice_input import transcriber


@pytest.fixture
def installed(monkeypatch, tmp_path):
    executable = tmp_path / "VoiceInputLocal"
    executable.touch()
    monkeypatch.setattr(transcriber, "local_executable", lambda: executable)
    return executable


def _completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


def test_a_stuck_child_is_given_up_on_instead_of_blocking_the_app(
    installed, monkeypatch
):
    def timed_out(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(transcriber.subprocess, "run", timed_out)
    with pytest.raises(ValueError):
        transcriber.transcribe_local(Path("recording.wav"))


def test_failures_log_diagnostics_but_never_the_transcript(installed, monkeypatch):
    logged = []
    monkeypatch.setattr(transcriber.logger, "error", logged.append)
    monkeypatch.setattr(
        transcriber.subprocess, "run",
        lambda *args, **kwargs: _completed(1, "文字起こし本文", "model missing"),
    )
    with pytest.raises(ValueError):
        transcriber.transcribe_local(Path("recording.wav"))
    assert "model missing" in logged[0]
    assert "文字起こし本文" not in logged[0]


def test_child_does_not_inherit_the_api_key_or_this_bundle(installed, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("_MEIPASS2", "/parent")
    monkeypatch.setenv("_PYI_ARCHIVE_FILE", "/parent")
    monkeypatch.setenv("DYLD_LIBRARY_PATH", "/parent/lib")
    monkeypatch.setenv("DYLD_LIBRARY_PATH_ORIG", "/original/lib")
    monkeypatch.setenv("DYLD_FRAMEWORK_PATH", "/parent/frameworks")
    captured = {}
    monkeypatch.setattr(
        transcriber.subprocess, "run",
        lambda *args, **kwargs: (
            captured.update(kwargs) or _completed(0, " 認識結果 \n")
        ),
    )

    assert transcriber.transcribe_local(Path("recording.wav")) == "認識結果"

    env = captured["env"]
    assert captured["timeout"] == transcriber.LOCAL_TRANSCRIBE_TIMEOUT
    assert "OPENAI_API_KEY" not in env
    assert not [name for name in env if name.startswith(("_PYI_", "_MEIPASS"))]
    assert env["DYLD_LIBRARY_PATH"] == "/original/lib"
    assert "DYLD_LIBRARY_PATH_ORIG" not in env
    assert "DYLD_FRAMEWORK_PATH" not in env


@pytest.mark.parametrize(("returncode", "ready"), [(0, True), (2, False)])
def test_probe_decides_whether_a_model_is_installed(
    installed, monkeypatch, returncode, ready
):
    monkeypatch.setattr(
        transcriber.subprocess, "run", lambda *args, **kwargs: _completed(returncode)
    )
    assert transcriber.local_model_ready() is ready


def test_probe_reports_not_ready_when_the_child_cannot_run(installed, monkeypatch):
    monkeypatch.setattr(
        transcriber.subprocess, "run", Mock(side_effect=OSError("exec failed"))
    )
    assert transcriber.local_model_ready() is False


def test_nothing_runs_until_the_local_app_is_installed(monkeypatch, tmp_path):
    monkeypatch.setattr(transcriber, "local_executable", lambda: tmp_path / "missing")
    run = Mock()
    monkeypatch.setattr(transcriber.subprocess, "run", run)
    assert transcriber.local_model_ready() is False
    with pytest.raises(ValueError):
        transcriber.transcribe_local(Path("recording.wav"))
    run.assert_not_called()
