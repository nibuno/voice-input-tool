import hashlib
import io
import threading
from unittest.mock import Mock

import pytest

from voice_input import local_models as module
from voice_input.local_models import DownloadCancelled, Model, ModelFile, ModelStore


@pytest.fixture
def store(tmp_path, monkeypatch):
    data = b"model bytes"
    file = ModelFile("weights.npz", len(data), hashlib.sha256(data).hexdigest())
    monkeypatch.setitem(
        module.MODELS,
        "test",
        Model(
            "test",
            "Test",
            "test/model",
            "a" * 40,
            (file,),
        ),
    )
    monkeypatch.setattr(
        module.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(data)
    )
    return ModelStore(tmp_path)


def test_verified_install_can_be_reused_without_network(store, monkeypatch):
    progress = Mock()
    store.download("test", progress, threading.Event())
    assert store.ready("test") and store.verify("test")
    progress.assert_called_with(11, 11)
    monkeypatch.setattr(
        module.urllib.request, "urlopen", Mock(side_effect=AssertionError)
    )
    store.download("test", progress, threading.Event())


def test_corrupt_download_is_never_marked_ready(store, monkeypatch):
    monkeypatch.setattr(
        module.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"bad")
    )
    with pytest.raises(ValueError):
        store.download("test", Mock(), threading.Event())
    assert not store.ready("test")
    assert not list(store.root.rglob("*.part"))


def test_cancelled_download_cleans_partial_file(store):
    cancel = threading.Event()
    with pytest.raises(DownloadCancelled):
        store.download("test", lambda *args: cancel.set(), cancel)
    assert not store.ready("test")
    assert not list(store.root.rglob("*.part"))


def test_same_size_tampering_is_detected(store):
    store.download("test", Mock(), threading.Event())
    (store.path("test") / "weights.npz").write_bytes(b"x" * 11)
    assert store.ready("test")  # UI check is deliberately inexpensive.
    assert not store.verify("test")


def test_interrupted_install_can_be_retried(store, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(module.urllib.request, "urlopen", Mock(side_effect=TimeoutError))
        with pytest.raises(TimeoutError):
            store.download("test", Mock(), threading.Event())
    store.download("test", Mock(), threading.Event())
    assert store.verify("test")
