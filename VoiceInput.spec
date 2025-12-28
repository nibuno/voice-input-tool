# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Voice Input app."""

import sys
from pathlib import Path

block_cipher = None

# Add src to path for imports
src_path = Path("src").absolute()

a = Analysis(
    ["src/voice_input/app.py"],
    pathex=[str(src_path)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "voice_input",
        "voice_input.transcriber",
        "voice_input.recorder",
        "voice_input.output",
        "voice_input.hotkey",
        "voice_input.config",
        "rumps",
        "pynput",
        "pynput.keyboard",
        "pynput.keyboard._darwin",
        "pynput._util",
        "pynput._util.darwin",
        "sounddevice",
        "scipy",
        "scipy.io",
        "scipy.io.wavfile",
        "numpy",
        "openai",
        "pyperclip",
        "pyautogui",
        "dotenv",
        "httpx",
        "httpcore",
        "certifi",
        "h11",
        "anyio",
        "sniffio",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VoiceInput",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="VoiceInput",
)

app = BUNDLE(
    coll,
    name="VoiceInput.app",
    icon=None,
    bundle_identifier="com.voiceinput.app",
    info_plist={
        "CFBundleName": "VoiceInput",
        "CFBundleDisplayName": "Voice Input",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "LSUIElement": True,
        "NSMicrophoneUsageDescription": "Voice Input needs microphone access to record audio for transcription.",
        "NSAppleEventsUsageDescription": "Voice Input needs accessibility access to paste transcribed text.",
    },
)
