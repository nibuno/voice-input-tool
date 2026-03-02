"""Configuration management for Voice Input Tool."""

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".voice-input"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "hotkey": "ctrl_l",
    "rms_threshold": 100,
    "input_device": None,
    "max_recording_seconds": 120.0,
}

VALID_HOTKEYS = ["ctrl_l", "ctrl_r", "alt_l", "alt_r"]


def load_config() -> dict:
    """Load configuration from file.

    Returns:
        Configuration dictionary. Returns default config if file doesn't exist.
    """
    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG.copy()

    try:
        with CONFIG_FILE.open() as f:
            config = json.load(f)
            # Validate hotkey value
            if config.get("hotkey") not in VALID_HOTKEYS:
                config["hotkey"] = DEFAULT_CONFIG["hotkey"]
            # Validate input_device type (devices are dynamic; actual resolution happens later)
            if "input_device" in config and not (
                config["input_device"] is None or isinstance(config["input_device"], str)
            ):
                config["input_device"] = DEFAULT_CONFIG["input_device"]
            return config
    except (json.JSONDecodeError, OSError):
        return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    """Save configuration to file.

    Args:
        config: Configuration dictionary to save.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_FILE.open("w") as f:
        json.dump(config, f, indent=2)
