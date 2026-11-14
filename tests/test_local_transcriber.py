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
    assert (
        engine.transcribe(np.array([-32768, 16384], dtype=np.int16).reshape(shape)) == "テストです。"
    )
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
