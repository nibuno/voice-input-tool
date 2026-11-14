"""Launch the standalone local edition, or exercise its bundled inference."""

import argparse
import fcntl
import os
import platform
from pathlib import Path

from .local_models import MODELS, ModelStore
from .local_paths import DATA_DIR


def configure_local_storage():
    from . import config, logger

    config.CONFIG_DIR = DATA_DIR
    config.CONFIG_FILE = DATA_DIR / "config.json"
    logger.LOG_DIR = Path.home() / "Library" / "Logs" / "VoiceInputLocal"


def main():
    parser = argparse.ArgumentParser(description="VoiceInput Local — offline Whisper")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--setup", action="store_true", help="Open permission settings")
    parser.add_argument("--models", action="store_true", help="Open model settings")
    parser.add_argument("--model", choices=MODELS, default=None)
    parser.add_argument(
        "--model-dir", type=Path, help="Override the model storage directory"
    )
    parser.add_argument(
        "--download-model", action="store_true", help="Download selected model"
    )
    parser.add_argument(
        "--transcribe", type=Path, help="Transcribe a mono 16 kHz PCM WAV"
    )
    parser.add_argument("--language", default="ja", help="Language for --transcribe")
    parser.add_argument("--self-test", action="store_true", help="Check the built app")
    args = parser.parse_args()
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        parser.error("VoiceInput Local requires an Apple Silicon Mac.")
    configure_local_storage()
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    from .config import load_config, save_config
    from .local_transcriber import LocalTranscriber

    if args.self_test:
        from .local_self_test import check_bundle

        check_bundle(ModelStore(args.model_dir) if args.model_dir else ModelStore())
        return

    config = load_config()
    key = args.model or config.get("local_model", "small")
    if key not in MODELS:
        key = "small"
    store = ModelStore(args.model_dir) if args.model_dir else ModelStore()
    if args.download_model:
        import threading

        store.download(key, lambda done, total: None, threading.Event())
        print(store.path(key))
        return
    if args.transcribe:
        from scipy.io import wavfile

        rate, audio = wavfile.read(args.transcribe)
        if rate != 16000 or audio.ndim != 1:
            parser.error("--transcribe requires a mono 16 kHz WAV file")
        print(LocalTranscriber(key, store).transcribe(audio, args.language))
        return

    import rumps

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # One global hotkey listener per edition. Keep the lock open until exit.
    with (DATA_DIR / ".instance.lock").open("a") as instance:
        try:
            fcntl.flock(instance, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            rumps.alert(
                "VoiceInput Local",
                "すでに起動しています。メニューバーを確認してください。",
            )
            return
        from . import permission_setup

        permission_setup.APPLICATION_NAME = "VoiceInput Local"
        show_permission_setup = permission_setup.show_permission_setup

        if args.setup:
            show_permission_setup(startup=True)
            return
        if args.models or not store.ready(key):
            from .model_setup import show_model_setup

            selected = show_model_setup(key, store)
            if not selected:
                return
            key = selected
            config["local_model"] = key
            save_config(config)
            if args.models:
                return
        from .permissions import ensure_permissions

        if not ensure_permissions():
            return
        # Import app only after storage is isolated and setup has completed.
        from .local_app import LocalVoiceInputApp
        from .logger import set_console_log_level
        import logging

        set_console_log_level(logging.DEBUG if args.debug else logging.INFO)
        LocalVoiceInputApp(LocalTranscriber(key, store), debug=args.debug).run()


if __name__ == "__main__":
    main()
