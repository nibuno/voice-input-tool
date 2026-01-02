"""Logging configuration for voice input application."""

import logging
from datetime import datetime
from pathlib import Path

# Log directory: ~/Library/Logs/VoiceInput/
LOG_DIR = Path.home() / "Library" / "Logs" / "VoiceInput"

# Logger name used throughout the application
LOGGER_NAME = "voice_input"


def get_logger() -> logging.Logger:
    """Get or create the application logger.

    Uses Python's built-in logger registry (singleton pattern).
    Handlers are configured only once on first call.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(LOGGER_NAME)

    # Already configured
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

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

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def set_console_log_level(level: int) -> None:
    """Set the console log level.

    Args:
        level: Logging level (e.g., logging.DEBUG, logging.INFO).
    """
    logger = logging.getLogger(LOGGER_NAME)
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, logging.FileHandler
        ):
            handler.setLevel(level)
            break


def log_exception(logger: logging.Logger, msg: str) -> None:
    """Log exception with full traceback.

    Args:
        logger: Logger instance.
        msg: Message prefix.
    """
    logger.exception(msg)
