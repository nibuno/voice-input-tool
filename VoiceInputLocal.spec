# -*- mode: python ; coding: utf-8 -*-
"""Standalone Apple Silicon build; model weights are downloaded in-app."""

import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

root = Path(SPECPATH)
datas = collect_data_files("mlx_whisper", includes=["assets/*"])
datas += collect_data_files("mlx", includes=["lib/*.metallib"])
datas += [(str(root / "build/local-notices"), "notices")]
datas += [(str(root / "src/voice_input/assets/nekochan"), "voice_input/assets/nekochan")]
datas += [(str(root / "tests/fixtures/voice-input.wav"), "voice_input")]
binaries = collect_dynamic_libs("mlx")

a = Analysis(
    [str(root / "src/voice_input/local_entry.py")],
    pathex=[str(root / "src")], binaries=binaries, datas=datas,
    hiddenimports=[
        "ApplicationServices", "AVFoundation", "HIServices",
        "pynput.keyboard._darwin", "pynput._util.darwin",
        "mlx.core", "mlx._reprlib_fix", "mlx.__array_api_info",
        "tiktoken_ext.openai_public",
    ],
    # torch is a conversion-only dependency of mlx-whisper, not inference.
    excludes=["torch", "torchaudio", "tensorflow", "matplotlib", "pandas",
              "mlx_whisper.torch_whisper"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="VoiceInputLocal",
    debug=False, strip=False, upx=False, console=False, argv_emulation=False,
    target_arch="arm64", codesign_identity=os.environ.get("CODESIGN_IDENTITY"),
    entitlements_file=str(root / "packaging/local-entitlements.plist"),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="VoiceInputLocal")
app = BUNDLE(
    coll, name="VoiceInputLocal.app", bundle_identifier="dev.nibuno.voiceinput.local",
    info_plist={
        "CFBundleName": "VoiceInput Local", "CFBundleDisplayName": "VoiceInput Local",
        "CFBundleVersion": "0.1.0", "CFBundleShortVersionString": "0.1.0",
        "LSMinimumSystemVersion": "15.0", "LSUIElement": True,
        "NSMicrophoneUsageDescription": "音声をMac内で文字に変換するためにマイクを使用します。",
    },
)
