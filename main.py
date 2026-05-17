"""Entry point for Manga Downloader.

Bridges asyncio with Qt via qasync so all async coroutines (fetch/download)
run inside the Qt event loop without blocking the UI.
"""
from __future__ import annotations
import sys
import asyncio
import io
import argparse

# Ensure UTF-8 output on Windows (avoids UnicodeEncodeError with emoji in logs)
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from PySide6.QtWidgets import QApplication
import qasync

from app.ui.mainWindow import MainWindow
from app.core.config import load_config, save_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manga Downloader")
    parser.add_argument("--output-dir", type=str, help="Output folder path")
    parser.add_argument(
        "--format",
        choices=["folder", "cbz", "pdf", "epub"],
        help="Download format",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    config = load_config()
    if args.output_dir:
        config.default_output_dir = args.output_dir
    if args.format:
        config.output_format = args.format

    app = QApplication(sys.argv)
    app.setApplicationName("Manga Downloader")
    app.setApplicationVersion("1.0.0")

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow(config=config)
    window.show()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
