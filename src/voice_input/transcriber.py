"""Whisper API transcription module."""

import os
import subprocess
import time
from pathlib import Path

from openai import OpenAI

from .logger import get_logger

logger = get_logger()


def transcribe(audio_path: Path, language: str = "ja") -> str:
    """Transcribe audio file using OpenAI Whisper API.

    Args:
        audio_path: Path to the audio file.
        language: Language code for transcription (default: "ja").

    Returns:
        Transcribed text.

    Raises:
        ValueError: If OPENAI_API_KEY is not set.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("Transcriber: OPENAI_API_KEY not set")
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    file_size = audio_path.stat().st_size
    logger.debug(
        f"Transcriber: Starting transcription for {audio_path} ({file_size} bytes)"
    )

    client = OpenAI(api_key=api_key)

    start_time = time.time()
    try:
        with open(audio_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=language,
                # temperature=0: ハルシネーション対策
                # Whisperは曖昧な音声に対して「ご視聴ありがとうございました」等の
                # トレーニングデータ由来のフレーズを誤出力することがある。
                # temperature=0にすると最も確率の高いトークンのみを選択し、
                # ランダム性を排除することでハルシネーションを軽減できる。
                # See: https://github.com/nibuno/voice-input-tool/issues/8
                temperature=0,
            )
        elapsed = time.time() - start_time
        logger.info(f"Transcriber: API call completed in {elapsed:.2f}s")
        logger.debug(
            f"Transcriber: Result: {response.text[:100]}..."
            if len(response.text) > 100
            else f"Transcriber: Result: {response.text}"
        )
        return response.text
    except Exception as e:
        elapsed = time.time() - start_time
        logger.exception(f"Transcriber: API call failed after {elapsed:.2f}s: {e}")
        raise


LOCAL_SETUP_HINT = "VoiceInputLocal.app をアプリケーションフォルダに入れてください。"
LOCAL_MODEL_HINT = "VoiceInputLocal を起動して、音声認識モデルの設定を終えてください。"
# The CLI starts a new process and loads the model every time, so allow for a
# slow first run on a cold file cache.
LOCAL_TRANSCRIBE_TIMEOUT = 120.0
LOCAL_PROBE_TIMEOUT = 20.0

# PyInstaller's bootloader exports these for its own use and saves whatever the
# dynamic loader was told before launch in ``*_ORIG``.
DYLD_VARIABLES = ("DYLD_LIBRARY_PATH", "DYLD_FRAMEWORK_PATH", "DYLD_INSERT_LIBRARIES")


def local_executable() -> Path:
    return Path("/Applications/VoiceInputLocal.app/Contents/MacOS/VoiceInputLocal")


def _local_environment() -> dict[str, str]:
    """Build the environment for the local edition's own bundle.

    This app may itself be running from a PyInstaller bundle, whose bootloader
    points the dynamic loader at *its* frameworks. A child process inherits
    that and would load the wrong libraries, so restore the pre-launch values
    and drop PyInstaller's private variables.
    """
    env = os.environ.copy()
    env.pop("OPENAI_API_KEY", None)
    for name in DYLD_VARIABLES:
        original = env.pop(f"{name}_ORIG", None)
        if original:
            env[name] = original
        else:
            env.pop(name, None)
    for name in [name for name in env if name.startswith(("_PYI_", "_MEIPASS"))]:
        del env[name]
    return env


def _run_local(*arguments: str, timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(local_executable()), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_local_environment(),
        timeout=timeout,
    )


def local_model_ready() -> bool:
    """Return True when the local edition has a model installed and ready."""
    if not local_executable().is_file():
        return False
    try:
        return _run_local("--probe", timeout=LOCAL_PROBE_TIMEOUT).returncode == 0
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning(f"Transcriber: local probe failed: {e}")
        return False


def transcribe_local(audio_path: Path) -> str:
    """Use the local edition's CLI and its already configured offline model."""
    if not local_executable().is_file():
        raise ValueError(LOCAL_SETUP_HINT)
    start_time = time.time()
    try:
        result = _run_local(
            "--transcribe", str(audio_path), timeout=LOCAL_TRANSCRIBE_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        # Without a timeout a stuck child would keep the processing counter
        # above zero forever, which blocks recording and the setup windows.
        logger.error(
            f"Transcriber: local recognition timed out "
            f"after {LOCAL_TRANSCRIBE_TIMEOUT:.0f}s"
        )
        raise ValueError(
            "ローカル認識が時間内に終わりませんでした。もう一度お試しください。"
        ) from None
    if result.returncode:
        # The transcript itself goes to stdout; only log the diagnostics.
        logger.error(
            f"Transcriber: local recognition exited with {result.returncode}: "
            f"{result.stderr.strip()[-500:] or '(no stderr output)'}"
        )
        raise ValueError(
            "ローカル認識に失敗しました。"
            "VoiceInputLocal のモデル設定を確認してください。"
        )
    elapsed = time.time() - start_time
    logger.info(f"Transcriber: local recognition finished in {elapsed:.2f}s")
    return result.stdout.strip()
