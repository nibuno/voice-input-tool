"""Native model selection and download window; workers never touch AppKit."""

import queue
import threading

import objc
from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSBackingStoreBuffered,
    NSBezelStyleRounded,
    NSButton,
    NSColor,
    NSFont,
    NSMakeRect,
    NSModalPanelRunLoopMode,
    NSPopUpButton,
    NSProgressIndicator,
    NSTextField,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskTitled,
)
from Foundation import NSObject, NSRunLoop, NSTimer

from .local_models import MODELS, DownloadCancelled, ModelStore


class ModelSetupController(NSObject):
    def init(self):
        self = objc.super(ModelSetupController, self).init()
        if self is None:
            return None
        self.store = ModelStore()
        self.selected = None
        self.busy = False
        self.cancel_event = threading.Event()
        self.events = queue.Queue()
        self.progress_value = (0, 1)
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, 620, 360),
            NSWindowStyleMaskTitled | NSWindowStyleMaskClosable,
            NSBackingStoreBuffered,
            False,
        )
        self.window.setTitle_("VoiceInput Local — 音声認識モデル")
        self.window.setReleasedWhenClosed_(False)
        self.window.setDelegate_(self)
        self.label("音声認識モデル", 24, 304, 572, 30, 20)
        self.label(
            "初回のダウンロード後は、インターネット接続もAPIキーも不要です。\n"
            "音声と文字起こしは、このMacの中で処理します。",
            24,
            244,
            572,
            48,
        )
        self.choice = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(22, 194, 576, 32), False
        )
        self.choice.addItemsWithTitles_([model.label for model in MODELS.values()])
        self.choice.setTarget_(self)
        self.choice.setAction_("selectionChanged:")
        self.window.contentView().addSubview_(self.choice)
        self.status = self.label("", 24, 146, 572, 38)
        self.progress = NSProgressIndicator.alloc().initWithFrame_(
            NSMakeRect(24, 124, 572, 14)
        )
        self.progress.setIndeterminate_(False)
        self.progress.setMaxValue_(1.0)
        self.window.contentView().addSubview_(self.progress)
        self.label("配布元：Hugging Face / mlx-community", 24, 85, 572, 24)
        self.cancel_button = self.button("閉じる", 324, "cancel:")
        self.action_button = self.button("ダウンロード", 460, "download:")
        self.action_button.setKeyEquivalent_("\r")
        self.selectionChanged_(None)
        self.window.center()
        return self

    @objc.python_method
    def label(self, text, x, y, width, height, size=13):
        label = NSTextField.wrappingLabelWithString_(text)
        label.setFrame_(NSMakeRect(x, y, width, height))
        label.setFont_(NSFont.systemFontOfSize_(size))
        label.setTextColor_(NSColor.labelColor())
        self.window.contentView().addSubview_(label)
        return label

    @objc.python_method
    def button(self, text, x, action):
        button = NSButton.alloc().initWithFrame_(NSMakeRect(x, 24, 136, 32))
        button.setTitle_(text)
        button.setBezelStyle_(NSBezelStyleRounded)
        button.setTarget_(self)
        button.setAction_(action)
        self.window.contentView().addSubview_(button)
        return button

    @objc.python_method
    def key(self):
        return list(MODELS)[self.choice.indexOfSelectedItem()]

    def selectionChanged_(self, _sender):
        ready = self.store.ready(self.key())
        self.status.setStringValue_(
            "ダウンロード済み。このモデルで音声入力できます。"
            if ready
            else "モデルをダウンロードしてください。途中でキャンセルできます。"
        )
        self.action_button.setTitle_("このモデルを使う" if ready else "ダウンロード")
        self.progress.setDoubleValue_(1.0 if ready else 0.0)

    def download_(self, _sender):
        if self.busy:
            return
        key = self.key()
        # Always verify the selected model off the UI thread, including cached files.
        self.busy = True
        self.cancel_event.clear()
        self.progress_value = (0, MODELS[key].size)
        self.action_button.setEnabled_(False)
        self.choice.setEnabled_(False)
        self.cancel_button.setTitle_("キャンセル")
        self.status.setStringValue_("モデルを確認しています…")
        threading.Thread(target=self.download_worker, args=(key,), daemon=True).start()

    @objc.python_method
    def download_worker(self, key):
        def progress(done, total):
            self.progress_value = (done, total)

        try:
            self.store.download(key, progress, self.cancel_event)
            self.events.put(("ready", key))
        except DownloadCancelled:
            self.events.put(("cancelled", None))
        except Exception as exc:  # noqa: BLE001 - network/filesystem boundary
            self.events.put(("error", str(exc)))

    def refresh_(self, _sender):
        if self.busy and not self.cancel_event.is_set():
            done, total = self.progress_value
            self.progress.setDoubleValue_(done / total)
            self.status.setStringValue_(
                f"モデルを準備中… {done / 1_000_000:.0f} / {total / 1_000_000:.0f} MB"
            )
        try:
            kind, value = self.events.get_nowait()
        except queue.Empty:
            return
        self.busy = False
        self.choice.setEnabled_(True)
        self.action_button.setEnabled_(True)
        self.cancel_button.setEnabled_(True)
        self.cancel_button.setTitle_("閉じる")
        if self.cancel_event.is_set():
            NSApplication.sharedApplication().stopModal()
        elif kind == "ready":
            self.selected = value
            NSApplication.sharedApplication().stopModal()
        else:
            self.status.setStringValue_(
                f"ダウンロードできませんでした。再試行できます。\n{value}"
            )
            self.action_button.setTitle_("再試行")

    def cancel_(self, _sender):
        if self.busy:
            self.cancel_event.set()
            self.cancel_button.setEnabled_(False)
            self.status.setStringValue_("キャンセル中… 通信の終了を待っています。")
        else:
            NSApplication.sharedApplication().stopModal()

    def windowShouldClose_(self, _sender):
        self.cancel_(None)
        return False

    @objc.python_method
    def run(self):
        app = NSApplication.sharedApplication()
        timer = NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(
            0.1, self, "refresh:", None, True
        )
        NSRunLoop.mainRunLoop().addTimer_forMode_(timer, NSModalPanelRunLoopMode)
        try:
            app.activateIgnoringOtherApps_(True)
            self.window.makeKeyAndOrderFront_(None)
            app.runModalForWindow_(self.window)
            return self.selected
        finally:
            timer.invalidate()
            self.window.orderOut_(None)
            self.window.setDelegate_(None)


def show_model_setup(key="small", store=None):
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    controller = ModelSetupController.alloc().init()
    controller.store = store or ModelStore()
    controller.choice.selectItemAtIndex_(list(MODELS).index(key))
    controller.selectionChanged_(None)
    return controller.run()
