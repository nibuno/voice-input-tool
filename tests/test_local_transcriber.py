import sys
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from voice_input.local_transcriber import LocalTranscriber


@pytest.mark.parametrize("shape", [(2,), (2, 1)])
def test_inference_uses_local_path_and_normalized_pcm(tmp_path, monkeypatch, shape):
    transcribe = Mock(return_value={"text": "  テストです。 "})
    monkeypatch.setitem(
        sys.modules, "mlx_whisper", SimpleNamespace(transcribe=transcribe)
    )
    store = Mock()
    store.path.return_value = tmp_path
    engine = LocalTranscriber(store=store)
    pcm = np.array([-32768, 16384], dtype=np.int16).reshape(shape)
    assert engine.transcribe(pcm) == "テストです。"
    args, kwargs = transcribe.call_args
    np.testing.assert_equal(args[0], [-1, 0.5])
    assert kwargs["path_or_hf_repo"] == str(tmp_path)
    assert kwargs["temperature"] == 0
    assert kwargs["language"] == "ja"
    store.download.assert_not_called()


def test_missing_or_corrupt_model_does_not_download_or_infer(monkeypatch):
    infer = Mock()
    monkeypatch.setitem(sys.modules, "mlx_whisper", SimpleNamespace(transcribe=infer))
    store = Mock()
    store.verify.return_value = False
    with pytest.raises(ValueError):
        LocalTranscriber(store=store).transcribe(np.ones(16000, dtype=np.int16))
    store.download.assert_not_called()
    infer.assert_not_called()


@pytest.mark.parametrize("verify_files", [True, False])
def test_hash_check_is_optional_but_the_revision_marker_is_not(
    tmp_path, monkeypatch, verify_files
):
    """Short-lived callers skip re-hashing the weights on every utterance."""
    infer = Mock(return_value={"text": "ok"})
    monkeypatch.setitem(sys.modules, "mlx_whisper", SimpleNamespace(transcribe=infer))
    store = Mock()
    store.path.return_value = tmp_path
    store.ready.return_value = True
    store.verify.return_value = False
    engine = LocalTranscriber(store=store, verify_files=verify_files)
    pcm = np.ones(16000, dtype=np.int16)
    if verify_files:
        with pytest.raises(ValueError):
            engine.transcribe(pcm)
        infer.assert_not_called()
    else:
        assert engine.transcribe(pcm) == "ok"
        store.verify.assert_not_called()

    store.ready.return_value = False
    with pytest.raises(ValueError):
        LocalTranscriber(store=store, verify_files=verify_files).transcribe(pcm)
