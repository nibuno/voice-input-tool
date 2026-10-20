"""Tests for desktop pet image resolution and reaction timing."""

from pathlib import Path

from voice_input.pet import (
    PET_REACTION_SECONDS,
    DesktopPet,
    PetState,
    resolve_pet_image,
    settled_state,
    state_after_status,
)


def test_resolve_pet_image_returns_none_when_missing(tmp_path: Path) -> None:
    assert resolve_pet_image(PetState.IDLE, tmp_path) is None


def test_resolve_pet_image_uses_state_name(tmp_path: Path) -> None:
    image = tmp_path / "listening.png"
    image.touch()

    assert resolve_pet_image(PetState.LISTENING, tmp_path) == image


def test_resolve_pet_image_prefers_gif(tmp_path: Path) -> None:
    (tmp_path / "idle.png").touch()
    gif = tmp_path / "idle.gif"
    gif.touch()

    assert resolve_pet_image(PetState.IDLE, tmp_path) == gif


def test_resolve_pet_image_uses_override(tmp_path: Path) -> None:
    (tmp_path / "happy.png").touch()
    custom = tmp_path / "nekochan_yatta.png"
    custom.touch()

    result = resolve_pet_image(
        PetState.HAPPY, tmp_path, {"happy": "nekochan_yatta.png"}
    )

    assert result == custom


def test_resolve_pet_image_missing_override_does_not_fall_back(
    tmp_path: Path,
) -> None:
    (tmp_path / "sad.png").touch()

    assert resolve_pet_image(PetState.SAD, tmp_path, {"sad": "missing.png"}) is None


def test_settled_state_keeps_reaction_until_duration() -> None:
    duration = PET_REACTION_SECONDS[PetState.HAPPY]

    assert settled_state(PetState.HAPPY, 10.0, 10.0 + duration - 0.1) == (
        PetState.HAPPY
    )
    assert settled_state(PetState.HAPPY, 10.0, 10.0 + duration) == PetState.IDLE


def test_settled_state_keeps_ongoing_states() -> None:
    assert settled_state(PetState.LISTENING, 0.0, 1000.0) == PetState.LISTENING
    assert settled_state(PetState.THINKING, 0.0, 1000.0) == PetState.THINKING


def test_state_after_status_resets_stuck_progress_states() -> None:
    assert state_after_status(PetState.LISTENING, is_recording=False) == PetState.IDLE
    assert state_after_status(PetState.THINKING, is_recording=False) == PetState.IDLE


def test_state_after_status_keeps_listening_while_recording() -> None:
    assert state_after_status(PetState.LISTENING, is_recording=True) == (
        PetState.LISTENING
    )


def test_state_after_status_lets_reactions_finish() -> None:
    assert state_after_status(PetState.HAPPY, is_recording=False) == PetState.HAPPY
    assert state_after_status(PetState.SAD, is_recording=False) == PetState.SAD


def test_pet_event_values_round_trip() -> None:
    # app.py sends reactions through the event queue as "pet:<value>".
    for state in PetState:
        assert PetState(state.value) is state


def test_hidden_pet_tracks_state_and_settles(tmp_path: Path) -> None:
    pet = DesktopPet(directory=tmp_path)

    pet.set_state(PetState.SAD, now=5.0)
    pet.tick(now=5.0 + PET_REACTION_SECONDS[PetState.SAD])

    assert pet.state == PetState.IDLE
