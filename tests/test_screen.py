"""Display selection across differently sized and vertically arranged screens."""
import sys
from types import SimpleNamespace
from unittest.mock import Mock

from voice_input import screen
from voice_input.pet import DesktopPet


def display(x, y, width, height):
    rect = SimpleNamespace(origin=SimpleNamespace(x=x, y=y),
                           size=SimpleNamespace(width=width, height=height))
    return SimpleNamespace(frame=lambda: rect, visibleFrame=lambda: rect)


def test_window_coordinates_use_primary_height_not_active_screen(monkeypatch):
    primary = display(0, 0, 1440, 900)
    upper = display(0, 900, 1920, 1080)
    ns = Mock()
    ns.screens.return_value = [primary, upper]
    ns.mainScreen.return_value = upper
    workspace = Mock()
    foreground = workspace.sharedWorkspace.return_value.frontmostApplication
    foreground.return_value.processIdentifier.return_value = 42
    quartz = SimpleNamespace(
        kCGWindowListOptionOnScreenOnly=1, kCGWindowListExcludeDesktopElements=2,
        kCGNullWindowID=0, kCGWindowOwnerPID='pid', kCGWindowLayer='layer',
        kCGWindowBounds='bounds', CGWindowListCopyWindowInfo=lambda *_: [
            {'pid': 42, 'layer': 0, 'bounds': {
                'X': 100, 'Y': -700, 'Width': 600, 'Height': 400,
            }},
        ],
    )
    monkeypatch.setitem(sys.modules, 'Quartz', quartz)
    monkeypatch.setitem(sys.modules, 'AppKit', SimpleNamespace(
        NSScreen=ns, NSWorkspace=workspace, NSEvent=Mock(),
    ))
    assert screen._frontmost_window_center() == (400, 1400)
    assert screen.target_screen() is upper


def test_window_screen_wins_over_mouse_screen(monkeypatch):
    primary = display(0, 0, 1440, 900)
    left = display(-1920, 0, 1920, 1080)
    ns = Mock()
    ns.screens.return_value = [primary, left]
    event = Mock()
    event.mouseLocation.return_value = SimpleNamespace(x=100, y=100)
    monkeypatch.setitem(
        sys.modules, 'AppKit', SimpleNamespace(NSScreen=ns, NSEvent=event)
    )
    monkeypatch.setattr(screen, '_frontmost_window_center', lambda: (-500, 500))
    assert screen.target_screen() is left
    monkeypatch.setattr(screen, '_frontmost_window_center', lambda: None)
    assert screen.target_screen() is primary


def test_pet_follows_while_visible_and_limits_polling(monkeypatch):
    pet = DesktopPet()
    position = Mock()
    monkeypatch.setattr(pet, '_position_panel', position)
    pet.tick(0)
    position.assert_not_called()
    pet._visible = True
    pet.tick(0)
    pet.tick(.1)
    position.assert_called_once()
    pet.tick(.3)
    assert position.call_count == 2
    pet._visible = False
    pet.tick(1)
    assert position.call_count == 2


def test_pet_moves_to_new_screen_without_moving_repeatedly(monkeypatch):
    from voice_input import pet as module
    from AppKit import NSMakePoint
    pet = DesktopPet()
    pet._panel = Mock()
    current = [display(0, 0, 1440, 900)]
    monkeypatch.setattr(module, 'target_screen', lambda: current[0])
    pet._position_panel()
    pet._position_panel()
    pet._panel.setFrameOrigin_.assert_called_once_with(NSMakePoint(1304, 24))
    current[0] = display(-1920, 0, 1920, 1080)
    pet._position_panel()
    pet._panel.setFrameOrigin_.assert_called_with(NSMakePoint(-136, 24))
