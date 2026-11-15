"""Explicit, cancellable downloads of pinned, checksum-verified Whisper models."""

import fcntl
import hashlib
import os
import shutil
import ssl
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import certifi

from .local_paths import MODEL_DIR


@dataclass(frozen=True)
class ModelFile:
    name: str
    size: int
    sha256: str


@dataclass(frozen=True)
class Model:
    key: str
    label: str
    repo: str
    revision: str
    files: tuple[ModelFile, ...]

    @property
    def size(self) -> int:
        return sum(file.size for file in self.files)


MODELS = {
    "small": Model(
        "small",
        "標準 — Whisper small（約481 MB）",
        "mlx-community/whisper-small-mlx",
        "45f3915923c7a79a5a5b5a7d909d39aeb0e5630e",
        (
            ModelFile(
                "config.json",
                266,
                "e8f58e638208af66d5d5d67801259dc7a12d199e971967a9f9d33a8e3635668e",
            ),
            ModelFile(
                "weights.npz",
                481307592,
                "55b6674c9b339702d486e2b1573839a66f8ec8f821ed2886993ef717a86b09f5",
            ),
        ),
    ),
    "turbo": Model(
        "turbo",
        "精度優先 — Whisper large-v3-turbo（約1.61 GB）",
        "mlx-community/whisper-large-v3-turbo",
        "a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb",
        (
            ModelFile(
                "config.json",
                268,
                "b34fc29e4e11e0a25e812775dd67f4dd16fc2c8eb43d28ae25ff7d660ecb6379",
            ),
            ModelFile(
                "weights.safetensors",
                1613977612,
                "951ed3fc1203e6a62467abb2144a96ce7eafca8fa77e3704fdb8635ff3e7f8a6",
            ),
        ),
    ),
}


class DownloadCancelled(Exception):
    pass


class ModelStore:
    def __init__(self, root: Path = MODEL_DIR):
        self.root = Path(root)

    def path(self, key: str) -> Path:
        model = MODELS[key]
        return self.root / f"{key}-{model.revision[:12]}"

    def ready(self, key: str) -> bool:
        """Cheap UI check; inference verifies full hashes before first use."""
        path = self.path(key)
        try:
            return (path / ".verified").read_text() == MODELS[key].revision and all(
                (path / f.name).stat().st_size == f.size for f in MODELS[key].files
            )
        except OSError:
            return False

    def verify(self, key: str) -> bool:
        try:
            for file in MODELS[key].files:
                path = self.path(key) / file.name
                if path.stat().st_size != file.size:
                    return False
                with path.open("rb") as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != file.sha256:
                        return False
            return True
        except OSError:
            return False

    def download(
        self,
        key: str,
        progress: Callable[[int, int], None],
        cancel: threading.Event,
    ) -> Path:
        model = MODELS[key]
        directory = self.path(key)
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / ".download.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("別のアプリがモデルを準備中です。") from exc
            if cancel.is_set():
                raise DownloadCancelled()
            if self.verify(key):
                (directory / ".verified").write_text(model.revision)
                progress(model.size, model.size)
                return directory
            (directory / ".verified").unlink(missing_ok=True)
            if shutil.disk_usage(directory).free < model.size + 100_000_000:
                raise OSError("モデル保存用の空き容量が不足しています。")
            done = 0
            context = ssl.create_default_context(cafile=certifi.where())
            for file in model.files:
                temporary = directory / (file.name + ".part")
                url = (
                    f"https://huggingface.co/{model.repo}/resolve/"
                    f"{model.revision}/{file.name}"
                )
                digest = hashlib.sha256()
                size = 0
                try:
                    request = urllib.request.Request(
                        url, headers={"User-Agent": "VoiceInputLocal/0.1"}
                    )
                    with (
                        urllib.request.urlopen(
                            request,
                            timeout=15,
                            context=context,
                        ) as response,
                        temporary.open("wb") as output,
                    ):
                        while True:
                            if cancel.is_set():
                                raise DownloadCancelled()
                            chunk = response.read(256 * 1024)
                            if not chunk:
                                break
                            size += len(chunk)
                            if size > file.size:
                                raise ValueError("モデルのサイズが一致しません。")
                            output.write(chunk)
                            digest.update(chunk)
                            progress(done + size, model.size)
                    if size != file.size or digest.hexdigest() != file.sha256:
                        raise ValueError(
                            "モデルの検証に失敗しました。再取得してください。"
                        )
                    if cancel.is_set():
                        raise DownloadCancelled()
                    os.replace(temporary, directory / file.name)
                    done += size
                finally:
                    temporary.unlink(missing_ok=True)
            (directory / ".verified").write_text(model.revision)
            return directory
