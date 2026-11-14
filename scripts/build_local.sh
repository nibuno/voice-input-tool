#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -m)" != "arm64" ]]; then
  echo "Build on an Apple Silicon Mac." >&2
  exit 1
fi
uv sync --extra local --extra dev --extra build --frozen
PYTHONPATH=src uv run --no-sync python -m pytest -q
uv run --no-sync python scripts/collect_local_notices.py
# A temporary build destination avoids Finder resource-fork metadata in synced folders.
build_output="$(mktemp -d /private/tmp/voice-input-local-build.XXXXXX)"
uv run --no-sync pyinstaller VoiceInputLocal.spec --noconfirm --distpath "$build_output"
codesign --verify --deep --strict "$build_output/VoiceInputLocal.app"
env -u PYTHONPATH -u OPENAI_API_KEY -u VIRTUAL_ENV \
  "$build_output/VoiceInputLocal.app/Contents/MacOS/VoiceInputLocal" --self-test
mkdir -p dist
# Replace only this generated bundle, so removed dependencies cannot survive a rebuild.
if [[ -d dist/VoiceInputLocal.app ]]; then
  rm -rf dist/VoiceInputLocal.app
fi
ditto "$build_output/VoiceInputLocal.app" dist/VoiceInputLocal.app
ditto -c -k --sequesterRsrc --keepParent dist/VoiceInputLocal.app dist/VoiceInputLocal-arm64.zip
echo "Created dist/VoiceInputLocal.app and dist/VoiceInputLocal-arm64.zip"
