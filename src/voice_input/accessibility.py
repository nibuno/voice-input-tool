"""Accessibility permission check for macOS."""

import ctypes
import ctypes.util


def check_accessibility_permission(prompt: bool = True) -> bool:
    """Check if the application has accessibility permission on macOS.

    Args:
        prompt: If True, show system dialog to request permission when not granted.

    Returns:
        True if permission is granted or not on macOS, False otherwise.
    """
    try:
        # Load CoreFoundation framework
        cf_path = ctypes.util.find_library("CoreFoundation")
        if cf_path is None:
            return True  # Not on macOS
        cf = ctypes.cdll.LoadLibrary(cf_path)

        # Load HIServices framework (contains AXIsProcessTrustedWithOptions)
        hi_path = ctypes.util.find_library("HIServices")
        if hi_path is None:
            # Try ApplicationServices as fallback (HIServices is a sub-framework)
            hi_path = ctypes.util.find_library("ApplicationServices")
        if hi_path is None:
            return True  # Framework not found, assume OK
        hi = ctypes.cdll.LoadLibrary(hi_path)

        # Set up CoreFoundation types
        CFStringRef = ctypes.c_void_p
        CFDictionaryRef = ctypes.c_void_p

        # Get kCFBooleanTrue
        cf.CFRetain.argtypes = [ctypes.c_void_p]
        cf.CFRetain.restype = ctypes.c_void_p
        kCFBooleanTrue = ctypes.c_void_p.in_dll(cf, "kCFBooleanTrue")

        # Create CFString for the option key
        cf.CFStringCreateWithCString.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_uint32,
        ]
        cf.CFStringCreateWithCString.restype = CFStringRef
        kCFStringEncodingUTF8 = 0x08000100

        option_key = cf.CFStringCreateWithCString(
            None,
            b"AXTrustedCheckOptionPrompt",
            kCFStringEncodingUTF8,
        )

        # Create CFDictionary with the option
        cf.CFDictionaryCreate.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        cf.CFDictionaryCreate.restype = CFDictionaryRef

        keys = (ctypes.c_void_p * 1)(option_key)
        values = (ctypes.c_void_p * 1)(kCFBooleanTrue if prompt else None)

        if prompt:
            options = cf.CFDictionaryCreate(
                None,
                keys,
                values,
                1,
                None,
                None,
            )
        else:
            options = None

        # Call AXIsProcessTrustedWithOptions
        hi.AXIsProcessTrustedWithOptions.argtypes = [CFDictionaryRef]
        hi.AXIsProcessTrustedWithOptions.restype = ctypes.c_bool

        result = hi.AXIsProcessTrustedWithOptions(options)

        # Clean up
        cf.CFRelease.argtypes = [ctypes.c_void_p]
        cf.CFRelease.restype = None
        if option_key:
            cf.CFRelease(option_key)
        if options:
            cf.CFRelease(options)

        return result

    except OSError:
        # Not on macOS or library not found
        return True
