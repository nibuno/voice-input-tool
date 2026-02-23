"""Monitors system sleep/wake and CoreAudio device list changes."""

import ctypes
import ctypes.util
import threading
from typing import Callable

from AppKit import NSWorkspace
from Foundation import NSObject

from .logger import get_logger

logger = get_logger()

# CoreAudio 4-char code constants (big-endian uint32)
_kAudioObjectSystemObject: int = 1
_kAudioHardwarePropertyDevices: int = 0x64657623   # 'dev#'
_kAudioObjectPropertyScopeGlobal: int = 0x676C6F62  # 'glob'
_kAudioObjectPropertyElementMain: int = 0


class _AudioObjectPropertyAddress(ctypes.Structure):
    _fields_ = [
        ("mSelector", ctypes.c_uint32),
        ("mScope", ctypes.c_uint32),
        ("mElement", ctypes.c_uint32),
    ]


_ListenerProc = ctypes.CFUNCTYPE(
    ctypes.c_int32,       # OSStatus return
    ctypes.c_uint32,      # inObjectID
    ctypes.c_uint32,      # inNumberAddresses
    ctypes.POINTER(_AudioObjectPropertyAddress),  # inAddresses
    ctypes.c_void_p,      # inClientData
)


class _SleepWakeObserver(NSObject):
    """NSObject subclass that receives NSWorkspace sleep/wake notifications."""

    # Declare as class attributes so PyObjC does not reserve these names
    # on the Objective-C side.  Instance assignments in _start_sleep_wake()
    # will shadow these with the actual callables.
    sleep_handler = None
    wake_handler = None

    def handleSleep_(self, notification) -> None:
        logger.debug("DeviceMonitor: NSWorkspaceWillSleepNotification received")
        if self.sleep_handler is not None:
            self.sleep_handler()

    def handleWake_(self, notification) -> None:
        logger.debug("DeviceMonitor: NSWorkspaceDidWakeNotification received")
        if self.wake_handler is not None:
            self.wake_handler()


class DeviceMonitor:
    """Monitors system sleep/wake and CoreAudio audio device list changes.

    Sleep/wake uses NSWorkspace notifications (delivered on the main thread).
    Device list changes use CoreAudio AudioObjectAddPropertyListener
    (callback arrives on a CoreAudio-internal thread).

    All callbacks may be invoked from non-main threads; callers should
    route them through a queue for UI thread safety.
    """

    def __init__(
        self,
        on_sleep: Callable[[], None],
        on_wake: Callable[[], None],
        on_device_change: Callable[[], None],
    ) -> None:
        self._on_sleep = on_sleep
        self._on_wake = on_wake
        self._on_device_change = on_device_change
        self._observer: _SleepWakeObserver | None = None
        self._ca_listener: _ListenerProc | None = None  # Must be kept alive to prevent GC
        self._ca_lib: ctypes.CDLL | None = None
        self._debounce_timer: threading.Timer | None = None
        self._debounce_lock = threading.Lock()

    def start(self) -> None:
        """Start sleep/wake and device change monitors."""
        self._start_sleep_wake()
        self._start_device_change()

    def stop(self) -> None:
        """Deregister all monitors and release resources."""
        if self._debounce_timer is not None:
            self._debounce_timer.cancel()
            self._debounce_timer = None

        if self._observer is not None:
            NSWorkspace.sharedWorkspace().notificationCenter().removeObserver_(
                self._observer
            )
            self._observer = None

        if self._ca_listener is not None and self._ca_lib is not None:
            addr = _AudioObjectPropertyAddress(
                _kAudioHardwarePropertyDevices,
                _kAudioObjectPropertyScopeGlobal,
                _kAudioObjectPropertyElementMain,
            )
            self._ca_lib.AudioObjectRemovePropertyListener(
                ctypes.c_uint32(_kAudioObjectSystemObject),
                ctypes.byref(addr),
                self._ca_listener,
                None,
            )
        self._ca_listener = None
        self._ca_lib = None

    def _start_sleep_wake(self) -> None:
        observer = _SleepWakeObserver.alloc().init()
        observer.sleep_handler = self._on_sleep
        observer.wake_handler = self._on_wake

        nc = NSWorkspace.sharedWorkspace().notificationCenter()
        nc.addObserver_selector_name_object_(
            observer, "handleSleep:", "NSWorkspaceWillSleepNotification", None
        )
        nc.addObserver_selector_name_object_(
            observer, "handleWake:", "NSWorkspaceDidWakeNotification", None
        )
        self._observer = observer
        logger.info("DeviceMonitor: sleep/wake monitor started")

    def _start_device_change(self) -> None:
        lib_path = ctypes.util.find_library("CoreAudio")
        if lib_path is None:
            logger.warning(
                "DeviceMonitor: CoreAudio library not found; "
                "device change monitoring disabled"
            )
            return

        try:
            ca_lib = ctypes.CDLL(lib_path)
        except OSError as exc:
            logger.warning(f"DeviceMonitor: Failed to load CoreAudio: {exc}")
            return

        dispatch = self._dispatch_device_change

        def _cb(object_id, num_addresses, addresses, client_data) -> int:
            dispatch()
            return 0  # noErr

        listener = _ListenerProc(_cb)
        addr = _AudioObjectPropertyAddress(
            _kAudioHardwarePropertyDevices,
            _kAudioObjectPropertyScopeGlobal,
            _kAudioObjectPropertyElementMain,
        )
        result = ca_lib.AudioObjectAddPropertyListener(
            ctypes.c_uint32(_kAudioObjectSystemObject),
            ctypes.byref(addr),
            listener,
            None,
        )
        if result != 0:
            logger.warning(
                f"DeviceMonitor: AudioObjectAddPropertyListener failed (err={result})"
            )
            return

        self._ca_lib = ca_lib
        self._ca_listener = listener  # Keep reference to prevent garbage collection
        logger.info("DeviceMonitor: device change monitor started")

    def _dispatch_device_change(self) -> None:
        """Debounce rapid-fire notifications into a single callback (0.5 s window)."""
        with self._debounce_lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
            timer = threading.Timer(0.5, self._on_device_change)
            timer.daemon = True
            timer.start()
            self._debounce_timer = timer
