"""CLI entry point for voice input tool."""

import argparse
import os

from dotenv import load_dotenv

from .output import output_text
from .recorder import record_and_save
from .transcriber import transcribe


def main() -> None:
    """Main entry point for the voice input tool."""
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Record voice and transcribe to text using Whisper API"
    )
    parser.add_argument(
        "-d",
        "--duration",
        type=float,
        default=5.0,
        help="Recording duration in seconds (default: 5)",
    )
    parser.add_argument(
        "--no-paste",
        action="store_true",
        help="Only copy to clipboard, don't paste",
    )
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is not set")
        return

    # Record audio
    audio_path = record_and_save(args.duration)

    try:
        # Transcribe
        print("Transcribing...")
        text = transcribe(audio_path)
        print(f"Transcribed: {text}")

        # Output
        if args.no_paste:
            from .output import copy_to_clipboard

            copy_to_clipboard(text)
            print("Copied to clipboard.")
        else:
            output_text(text)
            print("Pasted.")
    finally:
        # Clean up temp file
        audio_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
