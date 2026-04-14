"""Tests for the output dispatcher (copy_paste vs paste_enter modes)."""

from unittest.mock import MagicMock

import pytest

import voice_input.output as output


@pytest.fixture
def fake_clipboard(monkeypatch: pytest.MonkeyPatch):
    """Replace pyperclip with an in-memory mock that tracks copy/paste order."""
    state = {"current": "", "history": []}

    def fake_copy(value: str) -> None:
        state["current"] = value
        state["history"].append(value)

    def fake_paste() -> str:
        return state["current"]

    monkeypatch.setattr(output.pyperclip, "copy", fake_copy)
    monkeypatch.setattr(output.pyperclip, "paste", fake_paste)
    return state


@pytest.fixture
def stub_paste_and_enter(monkeypatch: pytest.MonkeyPatch):
    """Replace paste() and press_enter() with fakes so we can count calls."""
    calls = {"paste": 0, "enter": 0, "paste_error": None}

    def fake_paste():
        calls["paste"] += 1
        err = calls["paste_error"]
        if err is not None:
            raise err

    def fake_enter():
        calls["enter"] += 1

    monkeypatch.setattr(output, "paste", fake_paste)
    monkeypatch.setattr(output, "press_enter", fake_enter)
    # Avoid sleeping in tests.
    monkeypatch.setattr(output.time, "sleep", lambda _s: None)
    return calls


@pytest.fixture
def text_only_clipboard(monkeypatch: pytest.MonkeyPatch):
    """Force _clipboard_has_non_text_payload() to False for the test."""
    monkeypatch.setattr(output, "_clipboard_has_non_text_payload", lambda: False)


# ---------------------------------------------------------------------------
# copy_paste mode
# ---------------------------------------------------------------------------


def test_copy_paste_writes_text_and_pastes(
    fake_clipboard,
    stub_paste_and_enter,
):
    output.output_text("hello", mode="copy_paste")

    assert fake_clipboard["current"] == "hello"
    assert stub_paste_and_enter["paste"] == 1
    # copy_paste must NOT press Enter.
    assert stub_paste_and_enter["enter"] == 0


def test_default_mode_is_copy_paste(fake_clipboard, stub_paste_and_enter):
    output.output_text("hi")
    assert fake_clipboard["current"] == "hi"
    assert stub_paste_and_enter["enter"] == 0


# ---------------------------------------------------------------------------
# paste_enter mode
# ---------------------------------------------------------------------------


def test_paste_enter_restores_clipboard_and_submits(
    fake_clipboard,
    stub_paste_and_enter,
    text_only_clipboard,
):
    # Seed the clipboard with something the user copied earlier.
    fake_clipboard["current"] = "https://example.com"
    fake_clipboard["history"].clear()

    output.output_text("こんにちは", mode="paste_enter")

    # After the dust settles, the user's URL must be back on the clipboard.
    assert fake_clipboard["current"] == "https://example.com"
    # The transcription must have been on the clipboard at some point.
    assert "こんにちは" in fake_clipboard["history"]
    # Paste and Enter both fire exactly once.
    assert stub_paste_and_enter["paste"] == 1
    assert stub_paste_and_enter["enter"] == 1


def test_paste_enter_restores_even_when_paste_fails(
    fake_clipboard,
    stub_paste_and_enter,
    text_only_clipboard,
):
    fake_clipboard["current"] = "original"
    stub_paste_and_enter["paste_error"] = RuntimeError("paste kaput")

    with pytest.raises(RuntimeError, match="paste kaput"):
        output.output_text("new", mode="paste_enter")

    # try/finally must still restore the original clipboard content.
    assert fake_clipboard["current"] == "original"
    # No auto-submit when paste failed — avoids sending garbage to the target.
    assert stub_paste_and_enter["enter"] == 0


def test_paste_enter_skips_restore_for_non_text_clipboard(
    fake_clipboard,
    stub_paste_and_enter,
    monkeypatch: pytest.MonkeyPatch,
):
    """Non-text clipboards (images/files) cannot be round-tripped via pyperclip."""
    monkeypatch.setattr(output, "_clipboard_has_non_text_payload", lambda: True)
    # Clipboard starts with "whatever pyperclip reads from an image" — here just
    # an empty string as pyperclip would return for non-text content.
    fake_clipboard["current"] = ""

    output.output_text("new", mode="paste_enter")

    # We must NOT clobber the clipboard back to the (empty) text we read —
    # leaving the app's own "new" string there is marginally better than
    # erasing the user's image to an empty string, and the warning told them.
    # Final state is the transcription we just wrote.
    assert fake_clipboard["current"] == "new"
    # Still auto-submit: paste succeeded, that's what the user asked for.
    assert stub_paste_and_enter["enter"] == 1
