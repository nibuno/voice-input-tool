"""Menu setup must return immediately and reuse its nonmodal window."""
from types import SimpleNamespace
from unittest.mock import Mock

from voice_input import permission_setup as setup


def test_menu_setup_reuses_window_without_entering_modal_loop(monkeypatch):
    controller = Mock()
    factory = Mock()
    factory.alloc.return_value.init.return_value = controller
    monkeypatch.setattr(setup, 'PermissionSetupController', factory)
    monkeypatch.setattr(setup, '_open_controller', None)
    monkeypatch.setattr(setup, 'NSApplication', Mock())
    setup.show_permission_setup()
    setup.show_permission_setup()
    factory.alloc.assert_called_once()
    assert controller.show.call_count == 2
    controller.run.assert_not_called()


def test_dismiss_stops_refresh_and_releases_nonmodal_window(monkeypatch):
    controller = SimpleNamespace(modal=False, timer=Mock(), window=Mock())
    timer = controller.timer
    monkeypatch.setattr(setup, '_open_controller', controller)
    setup.PermissionSetupController.dismiss(controller)
    timer.invalidate.assert_called_once()
    controller.window.orderOut_.assert_called_once()
    assert setup._open_controller is None
    assert controller.timer is None


def test_startup_keeps_permission_gate_modal(monkeypatch):
    controller = Mock()
    controller.run.return_value = True
    factory = Mock()
    factory.alloc.return_value.init.return_value = controller
    monkeypatch.setattr(setup, 'PermissionSetupController', factory)
    monkeypatch.setattr(setup, 'NSApplication', Mock())
    assert setup.show_permission_setup(startup=True)
    controller.run.assert_called_once()
    controller.show.assert_not_called()
