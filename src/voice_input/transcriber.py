"""Whisper API transcription module."""

import os
from pathlib import Path

from openai import OpenAI


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
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    client = OpenAI(api_key=api_key)

    with open(audio_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=language,
        )

    return response.text
