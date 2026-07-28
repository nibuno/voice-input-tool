"""Tests for config module."""

import json
from pathlib import Path

import pytest

from voice_input.config import (
    DEFAULT_CONFIG,
    load_config,
    normalize_max_recording_seconds,
    save_config,
)


@pytest.fixture
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary config directory and patch module paths."""
    config_dir = tmp_path / ".voice-input"
    config_file = config_dir / "config.json"

    monkeypatch.setattr("voice_input.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("voice_input.config.CONFIG_FILE", config_file)

    return config_dir


class TestLoadConfig:
    """Tests for load_config function."""

    def test_returns_default_when_file_not_exists(self, config_dir: Path) -> None:
        # Act
        result = load_config()

        # Assert
        assert result == DEFAULT_CONFIG

    def test_returns_copy_of_default_config(self, config_dir: Path) -> None:
        # Act
        result = load_config()
        result["hotkey"] = "modified"

        # Assert
        assert DEFAULT_CONFIG["hotkey"] == "ctrl_l"

    def test_loads_valid_config_file(self, config_dir: Path) -> None:
        # Arrange
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.json"
        expected = {
            "hotkey": "ctrl_r",
            "rms_threshold": 200,
            "input_device": "Mic A",
            "max_recording_seconds": 30.0,
        }
        config_file.write_text(json.dumps(expected))

        # Act
        result = load_config()

        # Assert
        assert result == expected

    def test_replaces_invalid_hotkey_with_default(self, config_dir: Path) -> None:
        # Arrange
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.json"
        config_file.write_text(
            json.dumps({"hotkey": "invalid_key", "rms_threshold": 150})
        )

        # Act
        result = load_config()

        # Assert
        assert result["hotkey"] == DEFAULT_CONFIG["hotkey"]
        assert result["rms_threshold"] == 150

    def test_returns_default_when_json_is_invalid(self, config_dir: Path) -> None:
        # Arrange
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.json"
        config_file.write_text("{ invalid json }")

        # Act
        result = load_config()

        # Assert
        assert result == DEFAULT_CONFIG

    def test_invalid_input_device_type_falls_back(self, config_dir: Path) -> None:
        # Arrange
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.json"
        config_file.write_text(
            json.dumps({"hotkey": "ctrl_l", "rms_threshold": 100, "input_device": 123})
        )

        # Act
        result = load_config()

        # Assert
        assert result["input_device"] is None

    def test_invalid_max_recording_seconds_falls_back(self, config_dir: Path) -> None:
        # Arrange
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.json"
        config_file.write_text(
            json.dumps({"hotkey": "ctrl_l", "max_recording_seconds": -5})
        )

        # Act
        result = load_config()

        # Assert
        assert result["max_recording_seconds"] == DEFAULT_CONFIG["max_recording_seconds"]


class TestNormalizeMaxRecordingSeconds:
    """Tests for max recording duration normalization."""

    def test_accepts_positive_numbers(self) -> None:
        assert normalize_max_recording_seconds(45) == 45.0
        assert normalize_max_recording_seconds(12.5) == 12.5

    def test_rejects_non_positive_values(self) -> None:
        assert (
            normalize_max_recording_seconds(0)
            == DEFAULT_CONFIG["max_recording_seconds"]
        )
        assert (
            normalize_max_recording_seconds(-1)
            == DEFAULT_CONFIG["max_recording_seconds"]
        )

    def test_rejects_non_numeric_values(self) -> None:
        assert (
            normalize_max_recording_seconds("120")
            == DEFAULT_CONFIG["max_recording_seconds"]
        )
        assert (
            normalize_max_recording_seconds(True)
            == DEFAULT_CONFIG["max_recording_seconds"]
        )


class TestSaveConfig:
    """Tests for save_config function."""

    def test_creates_directory_if_not_exists(self, config_dir: Path) -> None:
        # Arrange
        config = {"hotkey": "alt_l", "rms_threshold": 50}

        # Act
        save_config(config)

        # Assert
        assert config_dir.exists()

    def test_saves_config_as_json(self, config_dir: Path) -> None:
        # Arrange
        config = {
            "hotkey": "alt_r",
            "rms_threshold": 75,
            "input_device": "Mic B",
            "max_recording_seconds": 45.0,
        }

        # Act
        save_config(config)

        # Assert
        config_file = config_dir / "config.json"
        saved = json.loads(config_file.read_text())
        assert saved == config
