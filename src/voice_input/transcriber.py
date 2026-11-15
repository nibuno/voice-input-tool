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


def local_executable() -> Path:
    return Path("/Applications/VoiceInputLocal.app/Contents/MacOS/VoiceInputLocal")


def transcribe_local(audio_path: Path) -> str:
    """Use the local edition's CLI and its already configured offline model."""
    if not local_executable().is_file():
        raise ValueError("VoiceInputLocal.app をアプリケーションフォルダに入れてください。")
    env = os.environ.copy()
    env.pop("OPENAI_API_KEY", None)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    result = subprocess.run(
        [str(local_executable()), "--transcribe", str(audio_path)],
        capture_output=True, text=True, encoding="utf-8", env=env,
    )
    if result.returncode:
        raise ValueError(
            "ローカル認識に失敗しました。VoiceInputLocal のモデル設定を確認してください。"
        )
    return result.stdout.strip()
