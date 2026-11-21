"""Exercise native controls and asynchronous setup without recording audio."""

import time
from unittest.mock import Mock

import pytest
from AppKit import NSApplication

from voice_input import model_setup
from voice_input.local_models import DownloadCancelled


@pytest.fixture
def controller(monkeypatch):
    NSApplication.sharedApplication()
    controller = model_setup.ModelSetupController.alloc().init()
    controller.store = Mock()
    controller.store.ready.return_value = False
    # StopModal is safe only within a modal loop. Tests inspect transitions directly.
    application = Mock()
    monkeypatch.setattr(
        model_setup,
        "NSApplication",
        Mock(
            sharedApplication=Mock(return_value=application),
        ),
    )
    yield controller, application
    controller.window.orderOut_(None)
    controller.window.setDelegate_(None)


def finish_worker(controller):
    deadline = time.monotonic() + 5
    while controller.events.empty() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not controller.events.empty(), "setup worker did not finish"
    controller.refresh_(None)


def test_model_selection_and_download_completion(controller):
    window, application = controller
    window.selectionChanged_(None)
    assert window.action_button.title() == "ダウンロード"
    assert window.choice.numberOfItems() == 2
    window.download_(None)
    finish_worker(window)
    assert window.selected == "small"
    assert not window.busy
    application.stopModal.assert_called_once()


def test_failed_download_allows_retry(controller):
    window, application = controller
    window.store.download.side_effect = OSError("offline")
    window.download_(None)
    finish_worker(window)
    assert window.selected is None
    assert window.action_button.isEnabled()
    assert window.action_button.title() == "再試行"
    application.stopModal.assert_not_called()


def test_cancel_waits_for_worker_before_closing(controller):
    window, application = controller

    def download(key, progress, cancel):
        assert cancel.wait(5)
        raise DownloadCancelled()

    window.store.download.side_effect = download
    window.download_(None)
    window.cancel_(None)
    finish_worker(window)
    assert window.selected is None
    application.stopModal.assert_called_once()


def test_native_modal_loop_delivers_worker_completion():
    """A real AppKit timer must close the modal loop after a worker finishes."""
    NSApplication.sharedApplication()
    window = model_setup.ModelSetupController.alloc().init()
    window.events.put(("ready", "small"))
    assert window.run() == "small"
    assert not window.window.isVisible()
