"""Minimal macOS floating panel for live transcription text."""

from __future__ import annotations

from .logger import get_logger

logger = get_logger()

OVERLAY_MAX_CHARACTERS = 110


def visible_transcript_tail(
    text: str,
    max_characters: int = OVERLAY_MAX_CHARACTERS,
) -> str:
    """Keep the newest transcript text visible within the four-line panel."""
    normalized = text.strip()
    if len(normalized) <= max_characters:
        return normalized
    return f"…{normalized[-max_characters:]}"


class TranscriptOverlay:
    """A non-interactive panel shown near the bottom of the main screen."""

    def __init__(self) -> None:
        self._panel = None
        self._label = None

    def _ensure_panel(self) -> None:
        if self._panel is not None:
            return

        from AppKit import (
            NSBackingStoreBuffered,
            NSColor,
            NSEvent,
            NSFont,
            NSLineBreakByWordWrapping,
            NSMakeRect,
            NSPanel,
            NSScreen,
            NSStatusWindowLevel,
            NSTextField,
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
            NSWindowCollectionBehaviorStationary,
            NSWindowStyleMaskBorderless,
            NSWindowStyleMaskNonactivatingPanel,
        )

        width = 760.0
        height = 156.0
        mouse = NSEvent.mouseLocation()
        target_screen = NSScreen.mainScreen()
        for candidate in NSScreen.screens():
            candidate_frame = candidate.frame()
            if (
                candidate_frame.origin.x
                <= mouse.x
                <= candidate_frame.origin.x + candidate_frame.size.width
                and candidate_frame.origin.y
                <= mouse.y
                <= candidate_frame.origin.y + candidate_frame.size.height
            ):
                target_screen = candidate
                break
        screen = target_screen.visibleFrame()
        x = screen.origin.x + (screen.size.width - width) / 2
        y = screen.origin.y + screen.size.height - height - 48.0
        frame = NSMakeRect(x, y, width, height)
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            frame,
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered,
            False,
        )
        panel.setLevel_(NSStatusWindowLevel)
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.colorWithWhite_alpha_(0.04, 0.96))
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

        label = NSTextField.labelWithString_("")
        label.setFrame_(NSMakeRect(28.0, 20.0, width - 56.0, height - 40.0))
        label.setTextColor_(NSColor.whiteColor())
        label.setFont_(NSFont.systemFontOfSize_weight_(22.0, 0.5))
        label.setLineBreakMode_(NSLineBreakByWordWrapping)
        label.setMaximumNumberOfLines_(4)
        panel.contentView().addSubview_(label)

        self._panel = panel
        self._label = label

    def show(self, text: str = "聞き取り中…") -> None:
        self._ensure_panel()
        self.update(text)
        self._panel.orderFrontRegardless()
        logger.info(
            "Transcript overlay shown (frame=%s, visible=%s)",
            self._panel.frame(),
            self._panel.isVisible(),
        )

    def update(self, text: str) -> None:
        self._ensure_panel()
        visible_text = visible_transcript_tail(text)
        self._label.setStringValue_(visible_text or "聞き取り中…")

    def hide(self) -> None:
        if self._panel is not None:
            self._panel.orderOut_(None)
            logger.debug("Transcript overlay hidden")
