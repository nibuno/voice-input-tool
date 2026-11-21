"""The build check must find its recording in the bundle and from source."""

from voice_input import local_self_test


def test_fixture_is_found_in_a_source_checkout():
    fixture = local_self_test.build_fixture()
    assert fixture.is_file()
    assert fixture.name == "voice-input.wav"


def test_the_copy_beside_the_module_wins_in_a_bundle(monkeypatch, tmp_path):
    bundled = tmp_path / "voice-input.wav"
    bundled.touch()
    monkeypatch.setattr(
        local_self_test, "__file__", str(tmp_path / "local_self_test.py")
    )
    assert local_self_test.build_fixture() == bundled


def test_a_missing_fixture_is_reported(monkeypatch, tmp_path):
    missing = tmp_path / "a" / "b" / "c" / "local_self_test.py"
    monkeypatch.setattr(local_self_test, "__file__", str(missing))
    try:
        local_self_test.build_fixture()
    except RuntimeError as error:
        assert "voice-input.wav" in str(error)
    else:
        raise AssertionError("expected a RuntimeError")
