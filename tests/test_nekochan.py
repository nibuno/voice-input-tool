"""Tests for Nekochan image resolution and reaction timing."""

from pathlib import Path

from voice_input.nekochan import (
    NEKOCHAN_REACTION_SECONDS,
    Nekochan,
    NekochanState,
    resolve_nekochan_image,
    settled_state,
    state_after_status,
)


def test_all_states_have_bundled_images(tmp_path: Path) -> None:
    for state in NekochanState:
        image = resolve_nekochan_image(state, tmp_path)
        assert image is not None
        assert image.stem == state.value
        assert image.is_file()


def test_legacy_image_directory(tmp_path, monkeypatch):
    from voice_input import nekochan

    directory = tmp_path / "nekochan"
    old_directory = tmp_path / "pet"
    old_directory.mkdir()
    image = old_directory / "idle.png"
    image.touch()
    monkeypatch.setattr(nekochan, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(nekochan, "NEKOCHAN_DIR", directory)
    assert resolve_nekochan_image(NekochanState.IDLE, directory) == image
    directory.mkdir()
    new_image = directory / image.name
    new_image.touch()
    assert resolve_nekochan_image(NekochanState.IDLE, directory) == new_image


def test_resolve_nekochan_image_uses_state_name(tmp_path: Path) -> None:
    image = tmp_path / "listening.png"
    image.touch()

    assert resolve_nekochan_image(NekochanState.LISTENING, tmp_path) == image


def test_resolve_nekochan_image_prefers_gif(tmp_path: Path) -> None:
    (tmp_path / "idle.png").touch()
    gif = tmp_path / "idle.gif"
    gif.touch()

    assert resolve_nekochan_image(NekochanState.IDLE, tmp_path) == gif


def test_resolve_nekochan_image_uses_override(tmp_path: Path) -> None:
    (tmp_path / "happy.png").touch()
    custom = tmp_path / "nekochan_yatta.png"
    custom.touch()

    result = resolve_nekochan_image(
        NekochanState.HAPPY, tmp_path, {"happy": "nekochan_yatta.png"}
    )

    assert result == custom


def test_resolve_nekochan_image_missing_override_does_not_fall_back(
    tmp_path: Path,
) -> None:
    (tmp_path / "sad.png").touch()

    assert (
        resolve_nekochan_image(NekochanState.SAD, tmp_path, {"sad": "missing.png"})
        is None
    )


def test_settled_state_keeps_reaction_until_duration() -> None:
    duration = NEKOCHAN_REACTION_SECONDS[NekochanState.HAPPY]

    assert settled_state(NekochanState.HAPPY, 10.0, 10.0 + duration - 0.1) == (
        NekochanState.HAPPY
    )
    assert (
        settled_state(NekochanState.HAPPY, 10.0, 10.0 + duration) == NekochanState.IDLE
    )


def test_settled_state_keeps_ongoing_states() -> None:
    assert (
        settled_state(NekochanState.LISTENING, 0.0, 1000.0) == NekochanState.LISTENING
    )
    assert settled_state(NekochanState.THINKING, 0.0, 1000.0) == NekochanState.THINKING


def test_state_after_status_resets_stuck_progress_states() -> None:
    assert (
        state_after_status(NekochanState.LISTENING, is_recording=False)
        == NekochanState.IDLE
    )
    assert (
        state_after_status(NekochanState.THINKING, is_recording=False)
        == NekochanState.IDLE
    )


def test_state_after_status_keeps_listening_while_recording() -> None:
    assert state_after_status(NekochanState.LISTENING, is_recording=True) == (
        NekochanState.LISTENING
    )


def test_state_after_status_lets_reactions_finish() -> None:
    assert (
        state_after_status(NekochanState.HAPPY, is_recording=False)
        == NekochanState.HAPPY
    )
    assert (
        state_after_status(NekochanState.SAD, is_recording=False) == NekochanState.SAD
    )


def test_nekochan_event_values_round_trip() -> None:
    # app.py sends reactions through the event queue as "nekochan:<value>".
    for state in NekochanState:
        assert NekochanState(state.value) is state


def test_hidden_nekochan_tracks_state_and_settles(tmp_path: Path) -> None:
    nekochan = Nekochan(directory=tmp_path)

    nekochan.set_state(NekochanState.SAD, now=5.0)
    nekochan.tick(now=5.0 + NEKOCHAN_REACTION_SECONDS[NekochanState.SAD])

    assert nekochan.state == NekochanState.IDLE
