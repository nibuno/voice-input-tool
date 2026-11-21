"""Storage isolated from the API edition; no credentials are used."""

from pathlib import Path

DATA_DIR = Path.home() / "Library" / "Application Support" / "VoiceInputLocal"
MODEL_DIR = DATA_DIR / "models"
