"""Tests for the live transcript panel text window."""

from voice_input.transcript_overlay import visible_transcript_tail


def test_visible_transcript_tail_keeps_short_text_unchanged() -> None:
    assert visible_transcript_tail(" 最新の音声入力 ", max_characters=20) == (
        "最新の音声入力"
    )


def test_visible_transcript_tail_follows_latest_text() -> None:
    text = "これは先頭の文章です。最後に表示したい文章です。"

    visible = visible_transcript_tail(text, max_characters=12)

    assert visible.startswith("…")
    assert visible.endswith("最後に表示したい文章です。"[-12:])
    assert "これは先頭" not in visible
