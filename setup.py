"""Setup script for py2app to create a macOS application bundle."""

from setuptools import setup

APP = ["src/voice_input/app.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "plist": {
        "CFBundleName": "VoiceInput",
        "CFBundleDisplayName": "Voice Input",
        "CFBundleIdentifier": "com.voiceinput.app",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "LSUIElement": True,  # Menu bar app (no dock icon)
        "NSMicrophoneUsageDescription": "Voice Input needs microphone access to record audio for transcription.",
        "NSAppleEventsUsageDescription": "Voice Input needs accessibility access to paste transcribed text.",
    },
    "packages": [
        "rumps",
        "pynput",
        "sounddevice",
        "scipy",
        "numpy",
        "openai",
        "pyperclip",
        "pyautogui",
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
