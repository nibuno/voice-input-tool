"""Permission checks must not prompt; setup must precede recording."""

import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from voice_input import permissions
from voice_input.permissions import PermissionStatus as Status


@pytest.fixture
def av(monkeypatch):
    module = SimpleNamespace(
        AVCaptureDevice=Mock(),
        AVMediaTypeAudio="audio",
        AVAuthorizationStatusNotDetermined=0,
        AVAuthorizationStatusRestricted=1,
        AVAuthorizationStatusDenied=2,
        AVAuthorizationStatusAuthorized=3,
    )
    monkeypatch.setitem(sys.modules, "AVFoundation", module)
    return module


@pytest.mark.parametrize("value, expected", [
    (0, Status.NOT_DETERMINED),
    (1, Status.RESTRICTED),
    (2, Status.DENIED),
    (3, Status.GRANTED),
    (99, Status.UNKNOWN),
])
def test_microphone_status_does_not_request_access(av, value, expected):
    av.AVCaptureDevice.authorizationStatusForMediaType_.return_value = value
    assert permissions.microphone_status() is expected
    av.AVCaptureDevice.requestAccessForMediaType_completionHandler_.assert_not_called()


def test_missing_framework_is_not_treated_as_permission(monkeypatch):
    monkeypatch.setitem(sys.modules, "AVFoundation", None)
    monkeypatch.setitem(sys.modules, "Quartz", None)
    assert permissions.microphone_status() is Status.UNKNOWN
    assert permissions.input_monitoring_status() is Status.UNKNOWN


@pytest.mark.parametrize("granted", [False, True])
def test_input_monitoring_check_does_not_request_access(monkeypatch, granted):
    quartz = SimpleNamespace(
        CGPreflightListenEventAccess=Mock(return_value=granted),
        CGRequestListenEventAccess=Mock(),
    )
    monkeypatch.setitem(sys.modules, "Quartz", quartz)
    expected = Status.GRANTED if granted else Status.DENIED
    assert permissions.input_monitoring_status() is expected
    quartz.CGRequestListenEventAccess.assert_not_called()


def test_poll_checks_accessibility_without_prompt(monkeypatch, av):
    check = Mock(return_value=True)
    monkeypatch.setattr(permissions, "check_accessibility_permission", check)
    monkeypatch.setattr(permissions, "input_monitoring_status", lambda: Status.GRANTED)
    av.AVCaptureDevice.authorizationStatusForMediaType_.return_value = 3
    assert permissions.permissions_ready(permissions.permission_statuses())
    check.assert_called_once_with(prompt=False)


@pytest.mark.parametrize("status", list(Status))
def test_ready_requires_all_three_permissions(status):
    states = dict.fromkeys(permissions.PERMISSIONS, Status.GRANTED)
    states["microphone"] = status
    assert permissions.permissions_ready(states) is (status is Status.GRANTED)
    del states["input_monitoring"]
    assert not permissions.permissions_ready(states)


def test_request_microphone_only_when_undetermined(av, monkeypatch):
    av.AVCaptureDevice.authorizationStatusForMediaType_.return_value = 0
    open_settings = Mock()
    monkeypatch.setattr(permissions, "open_permission_settings", open_settings)
    callback = Mock()
    assert permissions.request_permission("microphone", callback)
    av.AVCaptureDevice.requestAccessForMediaType_completionHandler_.assert_called_once_with(
        "audio", callback
    )
    open_settings.assert_not_called()


def test_denied_microphone_opens_settings_instead_of_reprompting(av, monkeypatch):
    av.AVCaptureDevice.authorizationStatusForMediaType_.return_value = 2
    open_settings = Mock(return_value=True)
    monkeypatch.setattr(permissions, "open_permission_settings", open_settings)
    assert permissions.request_permission("microphone")
    open_settings.assert_called_once_with("microphone")
    av.AVCaptureDevice.requestAccessForMediaType_completionHandler_.assert_not_called()


@pytest.mark.parametrize("key", ["accessibility", "input_monitoring"])
def test_request_registers_app_before_opening_settings(monkeypatch, key):
    calls = []
    monkeypatch.setattr(
        permissions, "check_accessibility_permission",
        lambda prompt: calls.append("request") or False,
    )
    monkeypatch.setitem(sys.modules, "Quartz", SimpleNamespace(
        CGRequestListenEventAccess=lambda: calls.append("request") or False
    ))
    monkeypatch.setattr(
        permissions, "open_permission_settings",
        lambda pane: calls.append(pane) or True,
    )
    assert permissions.request_permission(key)
    assert calls == ["request", key]


@pytest.mark.parametrize("completed", [False, True])
def test_setup_result_controls_startup(monkeypatch, completed):
    monkeypatch.setattr(permissions, "permission_statuses", lambda: {})
    show = Mock(return_value=completed)
    monkeypatch.setitem(sys.modules, "voice_input.permission_setup", SimpleNamespace(
        show_permission_setup=show
    ))
    assert permissions.ensure_permissions() is completed
    show.assert_called_once_with()


def test_existing_permissions_skip_setup(monkeypatch):
    monkeypatch.setattr(
        permissions, "permission_statuses",
        lambda: dict.fromkeys(permissions.PERMISSIONS, Status.GRANTED),
    )
    show = Mock()
    monkeypatch.setitem(sys.modules, "voice_input.permission_setup", SimpleNamespace(
        show_permission_setup=show
    ))
    assert permissions.ensure_permissions()
    show.assert_not_called()


def test_cancelled_setup_never_constructs_recording_app(monkeypatch):
    from voice_input import app

    monkeypatch.setattr(sys, "argv", ["voice-input-app"])
    monkeypatch.setattr(app, "ensure_permissions", lambda: False)
    create = Mock()
    monkeypatch.setattr(app, "VoiceInputApp", create)
    app.main()
    create.assert_not_called()


def test_setup_command_needs_no_api_key_or_recording_app(monkeypatch):
    from voice_input import app

    monkeypatch.setattr(sys, "argv", ["voice-input-app", "--setup"])
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    create = Mock()
    monkeypatch.setattr(app, "VoiceInputApp", create)
    show = Mock(return_value=True)
    monkeypatch.setitem(sys.modules, "voice_input.permission_setup", SimpleNamespace(
        show_permission_setup=show
    ))
    app.main()
    show.assert_called_once_with()
    create.assert_not_called()
