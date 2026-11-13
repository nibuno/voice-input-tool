"""Small always-on-top Nekochan that reacts to the app state."""

from collections.abc import Callable
from enum import Enum
from pathlib import Path

from AppKit import NSEvent, NSView

from .config import CONFIG_DIR
from .logger import get_logger
from .screen import target_screen

logger = get_logger()

NEKOCHAN_DIR = CONFIG_DIR / "nekochan"
BUNDLED_NEKOCHAN_DIR = Path(__file__).parent / "assets" / "nekochan"
NEKOCHAN_IMAGE_EXTENSIONS = (".gif", ".png")
NEKOCHAN_SIZE = 112.0
NEKOCHAN_SCREEN_MARGIN = 24.0
NEKOCHAN_EMOJI_FONT_SIZE = 72.0
NEKOCHAN_FOLLOW_INTERVAL = 0.25


class NekochanState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    HAPPY = "happy"
    SAD = "sad"


# Shown when no image is configured for a state.
NEKOCHAN_FALLBACK_EMOJI = {
    NekochanState.IDLE: "🐱",
    NekochanState.LISTENING: "👂",
    NekochanState.THINKING: "💭",
    NekochanState.HAPPY: "😸",
    NekochanState.SAD: "😿",
}

# Short-lived reactions fall back to IDLE after this many seconds.
NEKOCHAN_REACTION_SECONDS = {
    NekochanState.HAPPY: 2.5,
    NekochanState.SAD: 4.0,
}


def resolve_nekochan_image(
    state: NekochanState,
    directory: Path = NEKOCHAN_DIR,
    overrides: dict[str, str] | None = None,
) -> Path | None:
    """Return the image for ``state``, or None to use the fallback emoji.

    ``overrides`` maps a state name to a file name inside ``directory``.
    Without an override, local state images take priority over bundled ones.
    """
    directories = [directory]
    if directory == NEKOCHAN_DIR:
        directories.append(CONFIG_DIR / "pet")  # Images from earlier versions.
    override = (overrides or {}).get(state.value)
    if isinstance(override, str) and override:
        candidates = [root / override for root in directories]
    else:
        candidates = [
            root / f"{state.value}{ext}"
            for root in (*directories, BUNDLED_NEKOCHAN_DIR)
            for ext in NEKOCHAN_IMAGE_EXTENSIONS
        ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def settled_state(state: NekochanState, entered_at: float, now: float) -> NekochanState:
    """Return IDLE once a short-lived reaction has been shown long enough."""
    duration = NEKOCHAN_REACTION_SECONDS.get(state)
    if duration is not None and now - entered_at >= duration:
        return NekochanState.IDLE
    return state


def state_after_status(state: NekochanState, is_recording: bool) -> NekochanState:
    """Return the state to show after a status update from the app.

    Status updates arrive when recording or processing has finished without
    pasting (too short, no speech, stall recovery, ...). If the recorder is no
    longer running, an in-progress face would otherwise stay stuck forever.
    Reactions (HAPPY/SAD) are left alone so they can finish playing.
    """
    if state in (NekochanState.LISTENING, NekochanState.THINKING) and not is_recording:
        return NekochanState.IDLE
    return state


class NekochanDragView(NSView):
    def acceptsFirstMouse_(self, event):
        return True

    def mouseDown_(self, event):
        self.start_mouse = NSEvent.mouseLocation()
        self.start_origin = self.window().frame().origin
        self.nekochan._dragging = True

    def mouseDragged_(self, event):
        mouse = NSEvent.mouseLocation()
        self.window().setFrameOrigin_((
            self.start_origin.x + mouse.x - self.start_mouse.x,
            self.start_origin.y + mouse.y - self.start_mouse.y,
        ))

    def mouseUp_(self, event):
        self.nekochan._dragging = False
        if self.window().frame().origin != self.start_origin:
            self.nekochan._save_drag_offset()


class Nekochan:
    """A draggable panel positioned relative to the active screen.

    The panel must never become the key window: pasting targets the
    frontmost app, so stealing focus would send text to the wrong place.
    """

    def __init__(
        self,
        directory: Path = NEKOCHAN_DIR,
        overrides: dict[str, str] | None = None,
        offset=None,
        on_moved: Callable[[tuple[float, float]], None] | None = None,
    ) -> None:
        self._offset = (NEKOCHAN_SCREEN_MARGIN, NEKOCHAN_SCREEN_MARGIN)
        if isinstance(offset, (tuple, list)) and len(offset) == 2 and all(
            type(value) in (float, int) and 0 <= value <= 1e9 for value in offset
        ):
            self._offset = tuple(offset)
        self._on_moved = on_moved
        self._dragging = False
        self._directory = directory
        self._overrides = overrides
        self._state = NekochanState.IDLE
        self._entered_at = 0.0
        self._visible = False
        self._panel = None
        self._image_view = None
        self._emoji_label = None
        self._last_position_check = float("-inf")
        self._position = None

    @property
    def state(self) -> NekochanState:
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
            NSMakeRect(0.0, 0.0, NEKOCHAN_SIZE, NEKOCHAN_SIZE),
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered,
            False,
        )
        panel.setLevel_(NSStatusWindowLevel)
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setHasShadow_(False)
        panel.setIgnoresMouseEvents_(False)
        panel.setHidesOnDeactivate_(False)
        panel.setReleasedWhenClosed_(False)
        panel.setBecomesKeyOnlyIfNeeded_(True)
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorStationary
        )

        image_view = NSImageView.alloc().initWithFrame_(
            NSMakeRect(0.0, 0.0, NEKOCHAN_SIZE, NEKOCHAN_SIZE)
        )
        image_view.setImageScaling_(NSImageScaleProportionallyUpOrDown)
        # Plays animated GIFs without manual frame handling.
        image_view.setAnimates_(True)
        panel.contentView().addSubview_(image_view)

        emoji_height = NEKOCHAN_EMOJI_FONT_SIZE * 1.3
        emoji_label = NSTextField.labelWithString_("")
        emoji_label.setFrame_(
            NSMakeRect(
                0.0, (NEKOCHAN_SIZE - emoji_height) / 2, NEKOCHAN_SIZE, emoji_height
            )
        )
        emoji_label.setAlignment_(NSTextAlignmentCenter)
        emoji_label.setFont_(NSFont.systemFontOfSize_(NEKOCHAN_EMOJI_FONT_SIZE))
        panel.contentView().addSubview_(emoji_label)

        drag_view = NekochanDragView.alloc().initWithFrame_(panel.contentView().bounds())
        drag_view.nekochan = self
        panel.contentView().addSubview_(drag_view)

        self._panel = panel
        self._image_view = image_view
        self._emoji_label = emoji_label

    def _position_panel(self) -> None:
        from AppKit import NSMakePoint

        screen = target_screen()
        if screen is None:
            return
        frame = screen.visibleFrame()
        width = max(0, frame.size.width - NEKOCHAN_SIZE)
        height = max(0, frame.size.height - NEKOCHAN_SIZE)
        x = frame.origin.x + width - min(self._offset[0], width)
        y = frame.origin.y + min(self._offset[1], height)
        if self._position != (x, y):
            self._panel.setFrameOrigin_(NSMakePoint(x, y))
            self._position = (x, y)

    def _save_drag_offset(self) -> None:
        screen = self._panel.screen()
        if screen is None:
            return
        frame = screen.visibleFrame()
        origin = self._panel.frame().origin
        self._offset = (
            max(0, frame.origin.x + frame.size.width - NEKOCHAN_SIZE - origin.x),
            max(0, origin.y - frame.origin.y),
        )
        self._position = None
        self._position_panel()
        if self._on_moved:
            self._on_moved(self._offset)

    def _render(self) -> None:
        if self._panel is None:
            return

        from AppKit import NSImage

        image = None
        path = resolve_nekochan_image(self._state, self._directory, self._overrides)
        if path is not None:
            image = NSImage.alloc().initWithContentsOfFile_(str(path))
            if image is None:
                logger.warning("Nekochan: Could not load image %s", path)
        self._image_view.setImage_(image)
        self._image_view.setHidden_(image is None)
        self._emoji_label.setStringValue_(
            "" if image is not None else NEKOCHAN_FALLBACK_EMOJI[self._state]
        )

    def show(self) -> None:
        self._ensure_panel()
        self._position_panel()
        self._render()
        self._panel.orderFrontRegardless()
        self._visible = True
        logger.info("Nekochan shown (images from %s)", self._directory)

    def hide(self) -> None:
        self._visible = False
        self._dragging = False
        if self._panel is not None:
            self._panel.orderOut_(None)

    def set_state(self, state: NekochanState, now: float) -> None:
        self._entered_at = now
        if state == self._state:
            return
        self._state = state
        if self._visible:
            self._render()

    def tick(self, now: float) -> None:
        """Return to IDLE after a reaction has played; call from the main thread."""
        if (
            self._visible
            and not self._dragging
            and now - self._last_position_check >= NEKOCHAN_FOLLOW_INTERVAL
        ):
            self._position_panel()
            self._last_position_check = now
        settled = settled_state(self._state, self._entered_at, now)
        if settled != self._state:
            self.set_state(settled, now)
