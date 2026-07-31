"""Minimal PyInstaller entry point for the windowed macOS application."""

from ootp_radio.gui import main


if __name__ == "__main__":
    raise SystemExit(main())
