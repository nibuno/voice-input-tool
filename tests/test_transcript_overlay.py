"""Tests for the live transcript panel text window."""

from voice_input.transcript_overlay import (
    OVERLAY_RECENT_CHARACTERS,
    transcript_display_parts,
    visible_transcript_tail,
)


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


def test_transcript_display_parts_emphasizes_latest_text() -> None:
    text = "前の文脈" * 40 + "最新の発話"

    context, current = transcript_display_parts(text)

    assert len(current) == OVERLAY_RECENT_CHARACTERS
    assert current.endswith("最新の発話")
    assert context.startswith("…")


def test_transcript_display_parts_keeps_short_text_current() -> None:
    assert transcript_display_parts("短い発話") == ("", "短い発話")
