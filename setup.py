"""Setup script for py2app to create a macOS application bundle."""

from pathlib import Path
from runpy import run_path

from setuptools import setup

APP_VERSION = run_path(
    str(Path(__file__).parent / "src" / "voice_input" / "__init__.py")
)["__version__"]

APP = ["src/voice_input/app.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "plist": {
        "CFBundleName": "VoiceInput",
        "CFBundleDisplayName": "Voice Input",
        "CFBundleIdentifier": "com.voiceinput.app",
        "CFBundleVersion": APP_VERSION,
        "CFBundleShortVersionString": APP_VERSION,
        "LSUIElement": True,  # Menu bar app (no dock icon)
        "NSMicrophoneUsageDescription": "Voice Input needs microphone access to record audio for transcription.",
        "NSAppleEventsUsageDescription": "Voice Input needs accessibility access to paste transcribed text.",
    },
    "packages": [
        "rumps",
        "AVFoundation",
        "pynput",
        "sounddevice",
        "scipy",
        "numpy",
        "openai",
        "pyperclip",
        "dotenv",
    ],
    "includes": [
        "voice_input",
        "voice_input.transcriber",
        "voice_input.recorder",
        "voice_input.output",
        "voice_input.hotkey",
        "voice_input.config",
    ],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
