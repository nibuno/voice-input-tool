"""Logging configuration for voice input application."""

import logging
import os
from datetime import datetime
from pathlib import Path

# Log directory: ~/Library/Logs/VoiceInput/
LOG_DIR = Path.home() / "Library" / "Logs" / "VoiceInput"

# Global logger instance
_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    """Get or create the application logger.

    Returns:
        Configured logger instance.
    """
    global _logger
    if _logger is not None:
        return _logger

    _logger = logging.getLogger("voice_input")
    _logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers
    if _logger.handlers:
        return _logger

    # Create log directory
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # File handler with rotation by date
    log_file = LOG_DIR / f"voice_input_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    # Console handler (for CLI/debug mode)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Format
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    _logger.addHandler(file_handler)
    _logger.addHandler(console_handler)

    return _logger


def log_exception(logger: logging.Logger, msg: str) -> None:
    """Log exception with full traceback.

    Args:
        logger: Logger instance.
        msg: Message prefix.
    """
    logger.exception(msg)
