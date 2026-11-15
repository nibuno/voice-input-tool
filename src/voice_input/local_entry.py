"""Absolute entry point used by PyInstaller."""

if __name__ == "__main__":
    # Frozen helper processes (e.g. resource_tracker used by inference libraries)
    # must dispatch before parsing the desktop app's command-line arguments.
    import multiprocessing

    multiprocessing.freeze_support()
    from voice_input.local_main import main

    main()
