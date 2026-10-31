"""Offline inference. No download, API fallback, ffmpeg, or audio files."""

import os
import threading

import numpy as np

from .local_models import ModelStore


class LocalTranscriber:
    def __init__(self, key: str = "small", store: ModelStore | None = None):
        self.key = key
        self.store = store or ModelStore()
        self._verified = False
        self._lock = threading.Lock()

    def transcribe(self, audio: np.ndarray, language: str = "ja") -> str:
        """Accept mono 16 kHz int16 or normalized floating-point PCM."""
        with self._lock:
            if not self._verified:
                if not self.store.ready(self.key) or not self.store.verify(self.key):
                    raise ValueError("音声認識モデルを設定画面から再取得してください。")
                self._verified = True
            # Force the upstream loader offline even if a model is later removed.
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
            import mlx_whisper

            pcm = np.asarray(audio)
            if pcm.ndim != 1:
                raise ValueError("音声は16 kHzのモノラルで指定してください。")
            if pcm.dtype == np.int16:
                pcm = pcm.astype(np.float32) / 32768.0
            else:
                pcm = pcm.astype(np.float32)
            if not np.isfinite(pcm).all():
                raise ValueError("音声に不正な値が含まれています。")
            if not len(pcm):
                return ""
            result = mlx_whisper.transcribe(
                pcm,
                path_or_hf_repo=str(self.store.path(self.key).resolve()),
                language=language,
                temperature=0.0,
                verbose=None,
                condition_on_previous_text=False,
                word_timestamps=False,
            )
            return result["text"].strip()
