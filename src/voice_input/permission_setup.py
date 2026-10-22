"""Native permission setup window, also usable before the menu bar starts."""

import sys
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
    NSTextField,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskTitled,
)
from Foundation import NSObject, NSRunLoop, NSTimer

from .logger import get_logger
from .permissions import (
    PERMISSIONS,
    PermissionStatus,
    permission_statuses,
    permissions_ready,
    request_permission,
)

logger = get_logger()

SETUP_HINT = (
    "設定状況は自動で確認します。"
    "反映されない場合はアプリを起動し直してください。"
)
CHECK_FAILED_HINT = (
    "権限の状態を確認できません。アプリを再起動しても直らない場合は、"
    "アプリを再インストールしてください。"
)


class PermissionSetupController(NSObject):
    def init(self):
        self = objc.super(PermissionSetupController, self).init()
        if self is None:
            return None
        self.completed = False
        self.request_error = None
        self.microphone_pending = False
        self.microphone_response = threading.Event()
        self.status_labels = {}
        self.buttons = {}
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, 640, 500),
            NSWindowStyleMaskTitled | NSWindowStyleMaskClosable,
            NSBackingStoreBuffered,
            False,
        )
        self.window.setTitle_("Voice Input — 権限設定")
        self.window.setReleasedWhenClosed_(False)
        self.window.setDelegate_(self)

        self.label("音声入力に必要な権限", 24, 445, 592, 30, size=20)
        target = (
            "システム設定で Voice Input を許可してください。"
            if getattr(sys, "frozen", False)
            else "直接実行では、起動元のターミナルや Python が"
            "許可対象になる場合があります。"
        )
        self.label(target, 24, 405, 592, 36, secondary=True)

        for index, (key, (name, description)) in enumerate(PERMISSIONS.items()):
            y = 345 - index * 76
            self.label(name, 24, y, 240, 24, size=15)
            self.status_labels[key] = self.label(
                "", 270, y, 164, 24, secondary=True
            )
            self.label(description, 24, y - 38, 432, 36, secondary=True)
            self.buttons[key] = self.button(
                "設定を開く", 468, y - 8, 148, "requestPermission:"
            )

        self.message = self.label(
            SETUP_HINT,
            24, 109, 592, 40, secondary=True,
        )
        self.label(
            "初回の貼り付け時に「System Events」の操作を求められたら許可してください。",
            24, 65, 592, 36, secondary=True,
        )
        self.button("あとで", 380, 24, 104, "cancel:")
        self.done_button = self.button("完了", 496, 24, 120, "finish:")
        self.done_button.setKeyEquivalent_("\r")
        self.refresh_(None)
        self.window.center()
        return self

    @objc.python_method
    def label(self, text, x, y, width, height, size=13, secondary=False):
        label = NSTextField.wrappingLabelWithString_(text)
        label.setFrame_(NSMakeRect(x, y, width, height))
        label.setFont_(NSFont.systemFontOfSize_(size))
        if secondary:
            label.setTextColor_(NSColor.secondaryLabelColor())
        self.window.contentView().addSubview_(label)
        return label

    @objc.python_method
    def button(self, title, x, y, width, action):
        button = NSButton.alloc().initWithFrame_(NSMakeRect(x, y, width, 32))
        button.setTitle_(title)
        button.setBezelStyle_(NSBezelStyleRounded)
        button.setTarget_(self)
        button.setAction_(action)
        self.window.contentView().addSubview_(button)
        return button

    def refresh_(self, _sender):
        if self.microphone_response.is_set():
            self.microphone_pending = False
            self.microphone_response.clear()
        statuses = permission_statuses()
        for key, status in statuses.items():
            button = self.buttons[key]
            pending = key == "microphone" and self.microphone_pending
            self.status_labels[key].setStringValue_(
                "確認中…" if pending else status.value
            )
            button.setEnabled_(
                not pending
                and status not in (
                    PermissionStatus.GRANTED, PermissionStatus.RESTRICTED
                )
            )
            button.setTitle_(
                "許可する"
                if key == "microphone" and status is PermissionStatus.NOT_DETERMINED
                else "設定を開く"
            )
        self.done_button.setEnabled_(permissions_ready(statuses))
        self.message.setStringValue_(
            self.request_error
            or (
                CHECK_FAILED_HINT
                if PermissionStatus.UNKNOWN in statuses.values()
                else SETUP_HINT
            )
        )

    def requestPermission_(self, sender):
        key = next(key for key, button in self.buttons.items() if button == sender)
        self.request_error = None
        if key == "microphone":
            self.microphone_pending = (
                permission_statuses()[key] is PermissionStatus.NOT_DETERMINED
            )
        # AVFoundation calls back on a worker thread. The timer performs all
        # AppKit updates on the main thread, even after the window closes.
        response = self.microphone_response
        if not request_permission(key, lambda granted: response.set()):
            self.microphone_pending = False
            self.request_error = (
                "設定を開けませんでした。システム設定の"
                "「プライバシーとセキュリティ」から確認してください。"
            )
        self.refresh_(None)

    def finish_(self, _sender):
        # Recheck instead of relying on a potentially stale enabled button.
        if permissions_ready(permission_statuses()):
            self.completed = True
            NSApplication.sharedApplication().stopModal()

    def cancel_(self, _sender):
        NSApplication.sharedApplication().stopModal()

    def windowShouldClose_(self, _sender):
        self.cancel_(None)
        return True

    @objc.python_method
    def run(self) -> bool:
        app = NSApplication.sharedApplication()
        timer = NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(
            1.0, self, "refresh:", None, True
        )
        NSRunLoop.mainRunLoop().addTimer_forMode_(timer, NSModalPanelRunLoopMode)
        try:
            app.activateIgnoringOtherApps_(True)
            self.window.makeKeyAndOrderFront_(None)
            logger.info(
                "Permission setup shown (visible=%s, statuses=%s)",
                self.window.isVisible(),
                {key: status.name for key, status in permission_statuses().items()},
            )
            app.runModalForWindow_(self.window)
            return self.completed
        finally:
            timer.invalidate()
            self.window.orderOut_(None)
            self.window.setDelegate_(None)


def show_permission_setup(*, startup: bool = False) -> bool:
    app = NSApplication.sharedApplication()
    if startup:
        app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    controller = PermissionSetupController.alloc().init()
    return controller.run()
