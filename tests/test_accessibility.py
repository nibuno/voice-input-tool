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
    its return value and assert call arguments.
    """
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


def test_returns_true_when_pyobjc_unavailable(monkeypatch):
    """On non-macOS platforms ApplicationServices isn't importable; assume OK."""
    # Simulate ImportError by inserting a module that raises on attribute access.
    monkeypatch.setitem(sys.modules, "ApplicationServices", None)
    assert check_accessibility_permission() is True


def test_framework_exception_returns_false(fake_application_services):
    """Unexpected framework exception is logged and treated as 'not granted'."""
    fake_application_services.AXIsProcessTrustedWithOptions.side_effect = RuntimeError(
        "boom"
    )
    assert check_accessibility_permission(prompt=True) is False
