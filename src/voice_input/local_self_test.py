"""Offline build check. No microphone, global clipboard or event posting."""

from pathlib import Path

import Quartz
from AppKit import NSImage
from scipy.io import wavfile

from .local_models import ModelStore
from .local_transcriber import LocalTranscriber
from .nekochan import BUNDLED_NEKOCHAN_DIR, NekochanState, resolve_nekochan_image
from .output import RETURN_KEY, V_KEY, _key_events


def check_bundle(store: ModelStore) -> None:
    for state in NekochanState:
        image = resolve_nekochan_image(state, BUNDLED_NEKOCHAN_DIR)
        if image is None or not NSImage.alloc().initWithContentsOfFile_(str(image)):
            raise RuntimeError(f"Missing or unreadable Nekochan image: {state.value}")

    for key, command in [(V_KEY, True), (RETURN_KEY, False)]:
        flags = Quartz.kCGEventFlagMaskCommand if command else 0
        observed = [
            (Quartz.CGEventGetType(event), Quartz.CGEventGetFlags(event),
             Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode))
            for event in _key_events(key, command=command)
        ]
        if observed != [(Quartz.kCGEventKeyDown, flags, key),
                        (Quartz.kCGEventKeyUp, flags, key)]:
            raise RuntimeError(f"Unexpected keyboard events: {observed}")
    print("PASS: bundled images and native paste/Return events")

    model = next((key for key in ("small", "turbo") if store.ready(key)), None)
    if model is None:
        print("SKIP: offline speech recognition (no installed model)")
        return
    rate, frames = wavfile.read(Path(__file__).with_name("voice-input.wav"))
    if rate != 16000 or frames.ndim != 1:
        raise ValueError("Expected mono 16 kHz build fixture")
    # PortAudio delivers mono audio as (frames, 1).
    transcript = LocalTranscriber(model, store).transcribe(frames[:, None], "en")
    if "quick brown fox" not in transcript.casefold():
        raise RuntimeError(f"Unexpected fixture transcription: {transcript!r}")
    print(f"PASS: offline recognition ({model}): {transcript}")
