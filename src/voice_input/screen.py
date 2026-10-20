"""Choose the display containing the foreground application window."""

from .logger import get_logger

logger = get_logger()


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
            screens = NSScreen.screens()
            main_screen = screens[0] if screens else None
            if main_screen is None:
                return None
            appkit_y = main_screen.frame().size.height - quartz_y
            return quartz_x, appkit_y
    except (ImportError, AttributeError, TypeError, ValueError):
        logger.debug("Could not determine frontmost window position", exc_info=True)
    return None


def target_screen():
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

