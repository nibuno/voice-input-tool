"""Tests for the local edition's command-line entry point."""

import sys
from types import SimpleNamespace

import pytest

from voice_input import config as config_module
from voice_input import local_main


@pytest.fixture
def cli(monkeypatch, tmp_path):
    """Run main() without touching the real app support or config files."""
    monkeypatch.setattr(local_main.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(local_main.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(local_main, "configure_local_storage", lambda: None)
    monkeypatch.setattr(config_module, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / "config.json")


def _store(ready):
    return lambda *args, **kwargs: SimpleNamespace(ready=lambda key: ready)


def test_probe_reports_the_selected_model_when_it_is_ready(cli, monkeypatch, capsys):
    monkeypatch.setattr(local_main, "ModelStore", _store(True))
    monkeypatch.setattr(sys, "argv", ["VoiceInputLocal", "--probe"])
    local_main.main()
    assert capsys.readouterr().out.strip() == "small"


def test_probe_fails_before_a_model_is_installed(cli, monkeypatch):
    monkeypatch.setattr(local_main, "ModelStore", _store(False))
    monkeypatch.setattr(sys, "argv", ["VoiceInputLocal", "--probe"])
    with pytest.raises(SystemExit) as exit_info:
        local_main.main()
    assert exit_info.value.code != 0
