"""Tests for recording limit menu initialization and rebuilds."""

from unittest.mock import Mock

from voice_input.app import VoiceInputApp


class FakeMenuItem:
    """Minimal stand-in for a rumps submenu in unit tests."""

    def __init__(self, attached: bool) -> None:
        self._menu = object() if attached else None
        self.clear = Mock()
        self.added: list[object] = []

    def add(self, item: object) -> None:
        self.added.append(item)


def test_clear_menu_if_attached_skips_unattached_menu() -> None:
    menu = FakeMenuItem(attached=False)

    VoiceInputApp._clear_menu_if_attached(menu)

    menu.clear.assert_not_called()


def test_clear_menu_if_attached_clears_attached_menu() -> None:
    menu = FakeMenuItem(attached=True)

    VoiceInputApp._clear_menu_if_attached(menu)

    menu.clear.assert_called_once_with()
