#!/bin/bash
# Usage: bash scripts/verify_local_bundle.sh /path/to/models /path/to/16khz-mono.wav
set -euo pipefail
cd "$(dirname "$0")/.."
: "${1:?Specify the model directory}"
: "${2:?Specify a 16 kHz mono WAV file}"
model_directory="$1"
sample_audio="$2"
verification_directory="$(mktemp -d /private/tmp/voice-input-local-verify.XXXXXX)"
ditto -x -k dist/VoiceInputLocal-arm64.zip "$verification_directory"
app_bundle="$verification_directory/VoiceInputLocal.app"
codesign --verify --deep --strict "$app_bundle"
env -u OPENAI_API_KEY -u PYTHONPATH -u VIRTUAL_ENV \
  sandbox-exec -p '(version 1) (allow default) (deny network*)' \
  "$app_bundle/Contents/MacOS/VoiceInputLocal" \
  --model-dir "$model_directory" --transcribe "$sample_audio" \
  > "$verification_directory/transcript.txt" 2> "$verification_directory/stderr.txt"
if [[ ! -s "$verification_directory/transcript.txt" ]] || \
    grep -Eq 'Traceback|ModuleNotFoundError|resource_tracker|error:|\[PYI-.*ERROR' \
       "$verification_directory/stderr.txt"; then
  cat "$verification_directory/stderr.txt" >&2
  echo "Bundle verification failed: $verification_directory" >&2
  exit 1
fi
cat "$verification_directory/transcript.txt"
echo "Verified extracted bundle offline. Evidence: $verification_directory"
