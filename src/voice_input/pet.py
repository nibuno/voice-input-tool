"""Small always-on-top desktop pet that reacts to the app state."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from .config import CONFIG_DIR
from .logger import get_logger

logger = get_logger()

PET_DIR = CONFIG_DIR / "pet"
PET_IMAGE_EXTENSIONS = (".gif", ".png")
PET_SIZE = 112.0
PET_SCREEN_MARGIN = 24.0
PET_EMOJI_FONT_SIZE = 72.0


class PetState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    HAPPY = "happy"
    SAD = "sad"


# Shown when no image is configured for a state.
PET_FALLBACK_EMOJI = {
    PetState.IDLE: "🐱",
    PetState.LISTENING: "👂",
    PetState.THINKING: "💭",
    PetState.HAPPY: "😸",
    PetState.SAD: "😿",
}

# Short-lived reactions fall back to IDLE after this many seconds.
PET_REACTION_SECONDS = {
    PetState.HAPPY: 2.5,
    PetState.SAD: 4.0,
}


def resolve_pet_image(
    state: PetState,
    directory: Path = PET_DIR,
    overrides: dict[str, str] | None = None,
) -> Path | None:
    """Return the image for ``state``, or None to use the fallback emoji.

    ``overrides`` maps a state name to a file name inside ``directory``.
    Without an override, ``<state>.gif`` or ``<state>.png`` is used.
    """
    override = (overrides or {}).get(state.value)
    if isinstance(override, str) and override:
        candidates = [directory / override]
    else:
        candidates = [directory / f"{state.value}{ext}" for ext in PET_IMAGE_EXTENSIONS]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def settled_state(state: PetState, entered_at: float, now: float) -> PetState:
    """Return IDLE once a short-lived reaction has been shown long enough."""
    duration = PET_REACTION_SECONDS.get(state)
    if duration is not None and now - entered_at >= duration:
        return PetState.IDLE
    return state


class DesktopPet:
    """A non-interactive panel near the bottom-right corner of the main screen.

    The panel must never become the key window: pasting targets the
    frontmost app, so stealing focus would send text to the wrong place.
    """

    def __init__(
        self,
        directory: Path = PET_DIR,
        overrides: dict[str, str] | None = None,
    ) -> None:
        self._directory = directory
        self._overrides = overrides
        self._state = PetState.IDLE
        self._entered_at = 0.0
        self._visible = False
        self._panel = None
        self._image_view = None
        self._emoji_label = None

    @property
    def state(self) -> PetState:
        return self._state

    def _ensure_panel(self) -> None:
        if self._panel is not None:
            return

        from AppKit import (
            NSBackingStoreBuffered,
            NSColor,
            NSFont,
            NSImageScaleProportionallyUpOrDown,
            NSImageView,
            NSMakeRect,
            NSPanel,
            NSStatusWindowLevel,
            NSTextAlignmentCenter,
            NSTextField,
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
            NSWindowCollectionBehaviorStationary,
            NSWindowStyleMaskBorderless,
            NSWindowStyleMaskNonactivatingPanel,
        )

        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0.0, 0.0, PET_SIZE, PET_SIZE),
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered,
            False,
        )
        panel.setLevel_(NSStatusWindowLevel)
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setHasShadow_(False)
        panel.setIgnoresMouseEvents_(True)
        panel.setHidesOnDeactivate_(False)
        panel.setReleasedWhenClosed_(False)
        panel.setBecomesKeyOnlyIfNeeded_(True)
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorStationary
        )

        image_view = NSImageView.alloc().initWithFrame_(
            NSMakeRect(0.0, 0.0, PET_SIZE, PET_SIZE)
        )
        image_view.setImageScaling_(NSImageScaleProportionallyUpOrDown)
        # Plays animated GIFs without manual frame handling.
        image_view.setAnimates_(True)
        panel.contentView().addSubview_(image_view)

        emoji_height = PET_EMOJI_FONT_SIZE * 1.3
        emoji_label = NSTextField.labelWithString_("")
        emoji_label.setFrame_(
            NSMakeRect(0.0, (PET_SIZE - emoji_height) / 2, PET_SIZE, emoji_height)
        )
        emoji_label.setAlignment_(NSTextAlignmentCenter)
        emoji_label.setFont_(NSFont.systemFontOfSize_(PET_EMOJI_FONT_SIZE))
        panel.contentView().addSubview_(emoji_label)

        self._panel = panel
        self._image_view = image_view
        self._emoji_label = emoji_label

    def _position_panel(self) -> None:
        from AppKit import NSMakePoint, NSScreen

        screen = NSScreen.mainScreen()
        if screen is None:
            return
        frame = screen.visibleFrame()
        x = frame.origin.x + frame.size.width - PET_SIZE - PET_SCREEN_MARGIN
        y = frame.origin.y + PET_SCREEN_MARGIN
        self._panel.setFrameOrigin_(NSMakePoint(x, y))

    def _render(self) -> None:
        if self._panel is None:
            return

        from AppKit import NSImage

        image = None
        path = resolve_pet_image(self._state, self._directory, self._overrides)
        if path is not None:
            image = NSImage.alloc().initWithContentsOfFile_(str(path))
            if image is None:
                logger.warning("Pet: Could not load image %s", path)
        self._image_view.setImage_(image)
        self._image_view.setHidden_(image is None)
        self._emoji_label.setStringValue_(
            "" if image is not None else PET_FALLBACK_EMOJI[self._state]
        )

    def show(self) -> None:
        self._ensure_panel()
        self._position_panel()
        self._render()
        self._panel.orderFrontRegardless()
        self._visible = True
        logger.info("Pet shown (images from %s)", self._directory)

    def hide(self) -> None:
        self._visible = False
        if self._panel is not None:
            self._panel.orderOut_(None)

    def set_state(self, state: PetState, now: float) -> None:
        self._entered_at = now
        if state == self._state:
            return
        self._state = state
        if self._visible:
            self._render()

    def tick(self, now: float) -> None:
        """Return to IDLE after a reaction has played; call from the main thread."""
        settled = settled_state(self._state, self._entered_at, now)
        if settled != self._state:
            self.set_state(settled, now)
