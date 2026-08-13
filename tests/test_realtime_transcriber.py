"""Tests for realtime transcript state and PCM conversion."""

import base64

import numpy as np

from voice_input.realtime_transcriber import (
    REALTIME_SAMPLE_RATE,
    REALTIME_TRANSCRIPTION_MODEL,
    SEND_BATCH_SAMPLES,
    RealtimeTranscriber,
    TranscriptState,
)
from voice_input.recorder import SAMPLE_RATE


def test_transcript_state_replaces_partial_when_utterance_completes() -> None:
    state = TranscriptState()

    assert state.add_delta("今日は") == "今日は"
    assert state.add_delta("晴れ") == "今日は晴れ"
    assert state.complete("今日は晴れです") == "今日は晴れです"
    assert state.partial == ""


def test_transcript_state_keeps_previous_completed_utterances() -> None:
    state = TranscriptState()

    state.complete("最初の文")

    assert state.add_delta("次の") == "最初の文 次の"
    assert state.complete("次の文") == "最初の文 次の文"


def test_encode_chunk_converts_to_realtime_pcm_rate() -> None:
    chunk = np.arange(SAMPLE_RATE, dtype=np.int16).reshape(-1, 1)

    encoded = RealtimeTranscriber._encode_chunk(chunk)
    samples = np.frombuffer(base64.b64decode(encoded), dtype=np.int16)

    assert len(samples) == REALTIME_SAMPLE_RATE


def test_session_config_uses_japanese_realtime_transcription() -> None:
    config = RealtimeTranscriber._session_config()
    audio_input = config["audio"]["input"]

    assert config["type"] == "transcription"
    assert audio_input["format"] == {
        "type": "audio/pcm",
        "rate": REALTIME_SAMPLE_RATE,
    }
    assert audio_input["transcription"]["language"] == "ja"
    assert audio_input["transcription"]["model"] == REALTIME_TRANSCRIPTION_MODEL
    assert "prompt" not in audio_input["transcription"]
    assert audio_input["turn_detection"] is None


def test_next_audio_batch_combines_small_recorder_chunks() -> None:
    transcriber = RealtimeTranscriber(on_text=lambda _text: None)
    chunk_size = SEND_BATCH_SAMPLES // 4
    for _ in range(4):
        transcriber.submit(np.ones((chunk_size, 1), dtype=np.int16))

    batch = transcriber._next_audio_batch()

    assert batch is not None
    assert len(batch) == SEND_BATCH_SAMPLES


def test_send_audio_streams_batches_and_commits_once_on_stop() -> None:
    class FakeAudioBuffer:
        def __init__(self) -> None:
            self.append_calls = 0
            self.commit_calls = 0

        def append(self, *, audio: str) -> None:
            self.append_calls += 1

        def commit(self) -> None:
            self.commit_calls += 1

    class FakeConnection:
        def __init__(self) -> None:
            self.input_audio_buffer = FakeAudioBuffer()

    transcriber = RealtimeTranscriber(on_text=lambda _text: None)
    connection = FakeConnection()
    transcriber.submit(np.ones(SEND_BATCH_SAMPLES, dtype=np.int16))
    transcriber.stop()

    transcriber._send_audio(connection)

    assert connection.input_audio_buffer.append_calls == 1
    assert connection.input_audio_buffer.commit_calls == 1


def test_wait_for_final_transcript_returns_none_when_result_is_empty() -> None:
    transcriber = RealtimeTranscriber(on_text=lambda _text: None)
    transcriber._result_ready.set()

    assert transcriber.wait_for_final_transcript(timeout=0) is None


def test_wait_for_final_transcript_returns_committed_result() -> None:
    transcriber = RealtimeTranscriber(on_text=lambda _text: None)
    with transcriber._result_lock:
        transcriber._final_transcript = " 音声入力の結果 "
    transcriber._result_ready.set()

    assert transcriber.wait_for_final_transcript(timeout=0) == "音声入力の結果"
