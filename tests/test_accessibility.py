"""Tests for accessibility module."""

import sys
import types
from unittest.mock import MagicMock

import pytest

from voice_input.accessibility import check_accessibility_permission


@pytest.fixture
def fake_application_services(monkeypatch):
    """Install a fake ApplicationServices module exposing the two names we use.

    Returns the mock ``AXIsProcessTrustedWithOptions`` so tests can configure
    its return value and assert call arguments. Also pins sys.platform to
    "darwin" so the platform guard lets the check proceed.
    """
    monkeypatch.setattr(sys, "platform", "darwin")
    module = types.ModuleType("ApplicationServices")
    module.kAXTrustedCheckOptionPrompt = "AXTrustedCheckOptionPrompt"
    module.AXIsProcessTrustedWithOptions = MagicMock(return_value=True)
    monkeypatch.setitem(sys.modules, "ApplicationServices", module)
    return module


def test_returns_true_when_permission_granted(fake_application_services):
    fake_application_services.AXIsProcessTrustedWithOptions.return_value = True
    assert check_accessibility_permission(prompt=True) is True


def test_returns_false_when_permission_denied(fake_application_services):
    fake_application_services.AXIsProcessTrustedWithOptions.return_value = False
    assert check_accessibility_permission(prompt=True) is False


def test_prompt_true_passes_prompt_option(fake_application_services):
    check_accessibility_permission(prompt=True)
    (args, _) = fake_application_services.AXIsProcessTrustedWithOptions.call_args
    (options,) = args
    assert options == {fake_application_services.kAXTrustedCheckOptionPrompt: True}


def test_prompt_false_passes_none(fake_application_services):
    check_accessibility_permission(prompt=False)
    fake_application_services.AXIsProcessTrustedWithOptions.assert_called_once_with(None)


def test_returns_true_on_non_darwin(monkeypatch):
    """Non-macOS platforms skip the check entirely so the app can still start."""
    monkeypatch.setattr(sys, "platform", "linux")
    # Even if ApplicationServices is unavailable, we short-circuit before import.
    monkeypatch.setitem(sys.modules, "ApplicationServices", None)
    assert check_accessibility_permission() is True


def test_returns_false_when_pyobjc_import_fails_on_darwin(monkeypatch):
    """On macOS, an ImportError means pyobjc is broken — do not claim trust."""
    monkeypatch.setattr(sys, "platform", "darwin")
    # Setting the module entry to None causes `from ApplicationServices import ...`
    # to raise ImportError per the import system's contract.
    monkeypatch.setitem(sys.modules, "ApplicationServices", None)
    assert check_accessibility_permission() is False


def test_framework_exception_returns_false(fake_application_services):
    """Unexpected framework exception is logged and treated as 'not granted'."""
    fake_application_services.AXIsProcessTrustedWithOptions.side_effect = RuntimeError(
        "boom"
    )
    assert check_accessibility_permission(prompt=True) is False
