"""config モジュールのテスト."""

import json
from pathlib import Path

import pytest

from voice_input.config import (
    DEFAULT_CONFIG,
    VALID_HOTKEYS,
    load_config,
    save_config,
)


@pytest.fixture
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """テスト用の設定ディレクトリを作成し、モジュールのパスを差し替える."""
    config_dir = tmp_path / ".voice-input"
    config_file = config_dir / "config.json"

    monkeypatch.setattr("voice_input.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("voice_input.config.CONFIG_FILE", config_file)

    return config_dir


class TestLoadConfig:
    """load_config 関数のテスト."""

    def test_設定ファイルが存在しない場合はデフォルト設定を返す(
        self, config_dir: Path
    ) -> None:
        # Arrange
        # config_dir fixture により設定ファイルは存在しない状態

        # Act
        result = load_config()

        # Assert
        assert result == DEFAULT_CONFIG

    def test_デフォルト設定の変更が元の設定に影響しない(
        self, config_dir: Path
    ) -> None:
        # Arrange
        # config_dir fixture により設定ファイルは存在しない状態

        # Act
        result = load_config()
        result["hotkey"] = "modified"

        # Assert
        assert DEFAULT_CONFIG["hotkey"] == "ctrl_l"

    def test_有効な設定ファイルが存在する場合はその内容を返す(
        self, config_dir: Path
    ) -> None:
        # Arrange
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.json"
        expected = {"hotkey": "ctrl_r", "rms_threshold": 200}
        config_file.write_text(json.dumps(expected))

        # Act
        result = load_config()

        # Assert
        assert result == expected

    def test_無効なホットキーの場合はデフォルトのホットキーに置き換える(
        self, config_dir: Path
    ) -> None:
        # Arrange
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({"hotkey": "invalid_key", "rms_threshold": 150}))

        # Act
        result = load_config()

        # Assert
        assert result["hotkey"] == DEFAULT_CONFIG["hotkey"]
        assert result["rms_threshold"] == 150

    def test_JSONが壊れている場合はデフォルト設定を返す(
        self, config_dir: Path
    ) -> None:
        # Arrange
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.json"
        config_file.write_text("{ invalid json }")

        # Act
        result = load_config()

        # Assert
        assert result == DEFAULT_CONFIG


class TestSaveConfig:
    """save_config 関数のテスト."""

    def test_設定ディレクトリが存在しない場合でも保存できる(
        self, config_dir: Path
    ) -> None:
        # Arrange
        config = {"hotkey": "alt_l", "rms_threshold": 50}

        # Act
        save_config(config)

        # Assert
        config_file = config_dir / "config.json"
        assert config_file.exists()

    def test_設定がJSON形式で正しく保存される(self, config_dir: Path) -> None:
        # Arrange
        config = {"hotkey": "alt_r", "rms_threshold": 75}

        # Act
        save_config(config)

        # Assert
        config_file = config_dir / "config.json"
        saved = json.loads(config_file.read_text())
        assert saved == config


class TestValidHotkeys:
    """VALID_HOTKEYS 定数のテスト."""

    def test_有効なホットキーは4種類(self) -> None:
        # Assert
        assert len(VALID_HOTKEYS) == 4

    def test_左右のCtrlキーが含まれる(self) -> None:
        # Assert
        assert "ctrl_l" in VALID_HOTKEYS
        assert "ctrl_r" in VALID_HOTKEYS

    def test_左右のAltキーが含まれる(self) -> None:
        # Assert
        assert "alt_l" in VALID_HOTKEYS
        assert "alt_r" in VALID_HOTKEYS
