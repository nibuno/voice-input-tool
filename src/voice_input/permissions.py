"""macOS permission checks and explicit, user-initiated requests."""

from collections.abc import Callable
from enum import Enum

from .accessibility import check_accessibility_permission
from .logger import get_logger

logger = get_logger()


class PermissionStatus(Enum):
    GRANTED = "許可済み"
    NOT_DETERMINED = "未設定"
    DENIED = "未許可"
    RESTRICTED = "制限されています"
    UNKNOWN = "確認できません"


PERMISSIONS = {
    "microphone": ("マイク", "話した音声を録音します。"),
    "accessibility": (
        "アクセシビリティ",
        "文字起こししたテキストを、ほかのアプリに貼り付けます。",
    ),
    "input_monitoring": (
        "入力監視",
        "ほかのアプリの使用中も、録音用のホットキーを検知します。",
    ),
}

SETTINGS_PANES = {
    "microphone": "Privacy_Microphone",
    "accessibility": "Privacy_Accessibility",
    "input_monitoring": "Privacy_ListenEvent",
}


def microphone_status() -> PermissionStatus:
    try:
        import AVFoundation as av

        status = av.AVCaptureDevice.authorizationStatusForMediaType_(
            av.AVMediaTypeAudio
        )
        return {
            av.AVAuthorizationStatusAuthorized: PermissionStatus.GRANTED,
            av.AVAuthorizationStatusNotDetermined: PermissionStatus.NOT_DETERMINED,
            av.AVAuthorizationStatusDenied: PermissionStatus.DENIED,
            av.AVAuthorizationStatusRestricted: PermissionStatus.RESTRICTED,
        }.get(status, PermissionStatus.UNKNOWN)
    except Exception as exc:  # noqa: BLE001 - PyObjC framework boundary
        logger.warning("Microphone permission check failed: %s", exc)
        return PermissionStatus.UNKNOWN


def input_monitoring_status() -> PermissionStatus:
    try:
        from Quartz import CGPreflightListenEventAccess

        return (
            PermissionStatus.GRANTED
            if CGPreflightListenEventAccess()
            else PermissionStatus.DENIED
        )
    except Exception as exc:  # noqa: BLE001 - PyObjC framework boundary
        logger.warning("Input monitoring permission check failed: %s", exc)
        return PermissionStatus.UNKNOWN


def permission_statuses() -> dict[str, PermissionStatus]:
    """Read current OS state without triggering permission dialogs."""
    return {
        "microphone": microphone_status(),
        "accessibility": (
            PermissionStatus.GRANTED
            if check_accessibility_permission(prompt=False)
            else PermissionStatus.DENIED
        ),
        "input_monitoring": input_monitoring_status(),
    }


def permissions_ready(statuses: dict[str, PermissionStatus]) -> bool:
    # Require every known permission, including when a check failed.
    return all(statuses.get(key) is PermissionStatus.GRANTED for key in PERMISSIONS)


def open_permission_settings(key: str) -> bool:
    """Open the matching pane, with a general privacy-pane fallback."""
    from AppKit import NSWorkspace
    from Foundation import NSURL

    base = "x-apple.systempreferences:com.apple.preference.security"
    workspace = NSWorkspace.sharedWorkspace()
    if workspace.openURL_(NSURL.URLWithString_(f"{base}?{SETTINGS_PANES[key]}")):
        return True
    return bool(workspace.openURL_(NSURL.URLWithString_(f"{base}?Privacy")))


def request_permission(
    key: str, microphone_response: Callable[[bool], None] | None = None
) -> bool:
    """Request only the chosen permission; never record or send keystrokes."""
    try:
        if key == "microphone":
            if microphone_status() is PermissionStatus.NOT_DETERMINED:
                from AVFoundation import AVCaptureDevice, AVMediaTypeAudio

                AVCaptureDevice.requestAccessForMediaType_completionHandler_(
                    AVMediaTypeAudio, microphone_response or (lambda granted: None)
                )
                return True
        elif key == "accessibility":
            check_accessibility_permission(prompt=True)
        elif key == "input_monitoring":
            from Quartz import CGRequestListenEventAccess

            CGRequestListenEventAccess()
        return open_permission_settings(key)
    except Exception as exc:  # noqa: BLE001 - PyObjC framework boundary
        logger.warning("Permission request failed (%s): %s", key, exc)
        return False


def ensure_permissions() -> bool:
    """Gate startup before opening an audio stream or installing a hotkey tap."""
    if permissions_ready(permission_statuses()):
        return True
    from .permission_setup import show_permission_setup

    return show_permission_setup()
