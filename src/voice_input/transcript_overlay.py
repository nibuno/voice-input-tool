"""Minimal macOS floating panel for live transcription text."""

from __future__ import annotations

from .logger import get_logger

logger = get_logger()

OVERLAY_MAX_CHARACTERS = 110
OVERLAY_RECENT_CHARACTERS = 38
PANEL_WIDTH = 680.0
PANEL_HEIGHT = 132.0
PANEL_BOTTOM_MARGIN = 64.0
PANEL_CORNER_RADIUS = 18.0


def _frontmost_window_center() -> tuple[float, float] | None:
    """Return the frontmost app window center in AppKit screen coordinates."""
    try:
        import Quartz
        from AppKit import NSScreen, NSWorkspace

        application = NSWorkspace.sharedWorkspace().frontmostApplication()
        if application is None:
            return None
        pid = application.processIdentifier()
        options = (
            Quartz.kCGWindowListOptionOnScreenOnly
            | Quartz.kCGWindowListExcludeDesktopElements
        )
        windows = Quartz.CGWindowListCopyWindowInfo(
            options,
            Quartz.kCGNullWindowID,
        )
        for window in windows:
            if window.get(Quartz.kCGWindowOwnerPID) != pid:
                continue
            if window.get(Quartz.kCGWindowLayer, 0) != 0:
                continue
            bounds = window.get(Quartz.kCGWindowBounds)
            if not bounds:
                continue
            width = float(bounds.get("Width", 0.0))
            height = float(bounds.get("Height", 0.0))
            if width <= 0.0 or height <= 0.0:
                continue
            quartz_x = float(bounds.get("X", 0.0)) + width / 2
            quartz_y = float(bounds.get("Y", 0.0)) + height / 2
            main_screen = NSScreen.mainScreen()
            if main_screen is None:
                return None
            appkit_y = main_screen.frame().size.height - quartz_y
            return quartz_x, appkit_y
    except (ImportError, AttributeError, TypeError, ValueError):
        logger.debug("Could not determine frontmost window position", exc_info=True)
    return None


def visible_transcript_tail(
    text: str,
    max_characters: int = OVERLAY_MAX_CHARACTERS,
) -> str:
    """Keep the newest transcript text visible within the four-line panel."""
    normalized = text.strip()
    if len(normalized) <= max_characters:
        return normalized
    return f"…{normalized[-max_characters:]}"


def transcript_display_parts(text: str) -> tuple[str, str]:
    """Split visible text into muted context and the newest spoken phrase."""
    visible = visible_transcript_tail(text)
    if len(visible) <= OVERLAY_RECENT_CHARACTERS:
        return "", visible
    split_at = len(visible) - OVERLAY_RECENT_CHARACTERS
    return visible[:split_at], visible[split_at:]


class TranscriptOverlay:
    """A non-interactive panel shown near the bottom of the main screen."""

    def __init__(self) -> None:
        self._panel = None
        self._label = None

    def _target_screen(self):
        from AppKit import NSEvent, NSScreen

        point = _frontmost_window_center()
        if point is None:
            mouse = NSEvent.mouseLocation()
            point = mouse.x, mouse.y
        for candidate in NSScreen.screens():
            frame = candidate.frame()
            if (
                frame.origin.x <= point[0] <= frame.origin.x + frame.size.width
                and frame.origin.y <= point[1] <= frame.origin.y + frame.size.height
            ):
                return candidate
        return NSScreen.mainScreen()

    def _position_panel(self) -> None:
        from AppKit import NSMakePoint

        screen = self._target_screen().visibleFrame()
        x = screen.origin.x + (screen.size.width - PANEL_WIDTH) / 2
        y = screen.origin.y + PANEL_BOTTOM_MARGIN
        self._panel.setFrameOrigin_(NSMakePoint(x, y))

    def _ensure_panel(self) -> None:
        if self._panel is not None:
            return

        from AppKit import (
            NSBackingStoreBuffered,
            NSBox,
            NSBoxCustom,
            NSColor,
            NSFont,
            NSLineBreakByWordWrapping,
            NSMakeRect,
            NSMutableAttributedString,
            NSNoBorder,
            NSPanel,
            NSStatusWindowLevel,
            NSTextField,
            NSForegroundColorAttributeName,
            NSVisualEffectMaterialHUDWindow,
            NSVisualEffectBlendingModeBehindWindow,
            NSVisualEffectStateActive,
            NSVisualEffectView,
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
            NSWindowCollectionBehaviorStationary,
            NSWindowStyleMaskBorderless,
            NSWindowStyleMaskNonactivatingPanel,
        )

        width = PANEL_WIDTH
        height = PANEL_HEIGHT
        screen = self._target_screen().visibleFrame()
        x = screen.origin.x + (screen.size.width - width) / 2
        y = screen.origin.y + PANEL_BOTTOM_MARGIN
        frame = NSMakeRect(x, y, width, height)
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            frame,
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered,
            False,
        )
        panel.setLevel_(NSStatusWindowLevel)
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setHasShadow_(True)
        panel.setIgnoresMouseEvents_(True)
        panel.setHidesOnDeactivate_(False)
        panel.setReleasedWhenClosed_(False)
        panel.setBecomesKeyOnlyIfNeeded_(True)
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorStationary
        )

        surface = NSVisualEffectView.alloc().initWithFrame_(
            NSMakeRect(0.0, 0.0, width, height)
        )
        surface.setMaterial_(NSVisualEffectMaterialHUDWindow)
        surface.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
        surface.setState_(NSVisualEffectStateActive)
        surface.setWantsLayer_(True)
        surface.layer().setCornerRadius_(PANEL_CORNER_RADIUS)
        surface.layer().setMasksToBounds_(True)
        panel.contentView().addSubview_(surface)

        recording_dot = NSBox.alloc().initWithFrame_(
            NSMakeRect(22.0, 103.0, 8.0, 8.0)
        )
        recording_dot.setBoxType_(NSBoxCustom)
        recording_dot.setBorderType_(NSNoBorder)
        recording_dot.setFillColor_(
            NSColor.systemRedColor().colorWithAlphaComponent_(0.9)
        )
        recording_dot.setCornerRadius_(4.0)
        surface.addSubview_(recording_dot)

        label = NSTextField.labelWithString_("")
        label.setFrame_(NSMakeRect(42.0, 18.0, width - 66.0, height - 36.0))
        label.setTextColor_(NSColor.blackColor())
        label.setFont_(NSFont.systemFontOfSize_weight_(19.0, 0.35))
        label.setLineBreakMode_(NSLineBreakByWordWrapping)
        label.setMaximumNumberOfLines_(4)
        surface.addSubview_(label)

        self._panel = panel
        self._label = label
        self._attributed_string_class = NSMutableAttributedString
        self._foreground_color_attribute = NSForegroundColorAttributeName
        self._muted_text_color = NSColor.blackColor().colorWithAlphaComponent_(0.5)
        self._current_text_color = NSColor.blackColor().colorWithAlphaComponent_(0.9)

    def show(self, text: str = "聞き取り中…") -> None:
        self._ensure_panel()
        self._position_panel()
        self.update(text)
        self._panel.orderFrontRegardless()
        logger.info(
            "Transcript overlay shown (frame=%s, visible=%s)",
            self._panel.frame(),
            self._panel.isVisible(),
        )

    def update(self, text: str) -> None:
        self._ensure_panel()
        context, current = transcript_display_parts(text)
        visible_text = f"{context}{current}" or "聞き取り中…"
        attributed = self._attributed_string_class.alloc().initWithString_(
            visible_text
        )
        if context:
            attributed.addAttribute_value_range_(
                self._foreground_color_attribute,
                self._muted_text_color,
                (0, len(context)),
            )
        attributed.addAttribute_value_range_(
            self._foreground_color_attribute,
            self._current_text_color,
            (len(context), len(visible_text) - len(context)),
        )
        self._label.setAttributedStringValue_(attributed)

    def hide(self) -> None:
        if self._panel is not None:
            self._panel.orderOut_(None)
            logger.debug("Transcript overlay hidden")
