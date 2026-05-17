# CLAUDE.md

Rules and context for Claude Code when working in this repository.

---

## Context

`tool_manga_downloader` — PySide6 desktop app that downloads manga from Vietnamese websites for offline reading.

**Stack**: Python 3.10+, PySide6 (Qt6 GUI), aiohttp (async HTTP), BeautifulSoup4 (HTML parsing), qasync (asyncio ↔ Qt bridge)

---

## Dev Commands

```powershell
# Run tests
pytest

# Run tests with coverage
pytest --cov=app --cov-report=html

# Lint & format
black app/ tests/
ruff check app/ tests/
mypy app/
```

> For installation and running the app, see README.md.

---

## Architecture

```
tool_manga_downloader/
├── main.py                     # Entry point: QApplication + qasync event loop + CLI args (--output-dir, --format)
├── run.bat                     # Windows launcher — always runs background via pythonw.exe
├── run.sh                      # Bash launcher
├── output/manga/               # Default download output (gitignored)
├── app/
│   ├── core/
│   │   ├── models.py           # Manga, Chapter dataclasses + ExportFormat, DownloadStatus enums
│   │   ├── config.py           # AppConfig dataclass; default_output_dir = project_root/output/manga
│   │   ├── downloader.py       # MangaDownloader + DownloadSignals; output path includes format subfolder
│   │   └── exporter.py         # Export to CBZ / PDF / EPUB / Folder
│   ├── sites/
│   │   ├── base.py             # BaseSite ABC
│   │   ├── registry.py         # SITES list + get_site_for_url()
│   │   └── truyenqqko.py       # TruyenQQKo site plugin
│   ├── ui/
│   │   ├── mainWindow.py       # QMainWindow; accepts optional AppConfig via __init__(config=)
│   │   └── settingsDialog.py   # Settings QDialog
│   └── utils/
│       ├── naming.py           # zero_pad(), sanitize_filename(), image_filename()
│       ├── headers.py          # USER_AGENTS list, get_random_ua(), get_default_headers()
│       └── logger.py           # logger singleton
└── tests/
    ├── conftest.py             # Fixtures: sample_manga_html, sample_chapter_html
    ├── fixtures/               # Saved HTML for offline parser tests
    ├── test_models.py
    ├── test_naming.py
    └── test_parser_truyenqqko.py
```

---

## Key Design Decisions

These are invariants — do not break them without explicit user approval.

- **qasync**: The asyncio event loop IS the Qt event loop. Never use `asyncio.run()` inside the UI thread. All async ops run in the main thread.
- **DownloadSignals**: Plain callback object (not Qt signals) so `MangaDownloader` stays testable without a Qt app.
- **Plugin system**: Each site subclasses `BaseSite`. Register by adding to `SITES` list in `registry.py`. Never hardcode site logic outside a plugin file.
- **Resume**: Skip an image if the file already exists and `stat().st_size > 100`. Do not re-download.
- **Output structure**: `<output_dir>/<MangaTitle>/<format>/Chapter_XXXX/001.jpg`. The format subfolder (`cbz`, `pdf`, `epub`, `folder`) is always present.
- **Default output dir**: Resolved at import time via `Path(__file__).parents[2] / "output" / "manga"` in `config.py` — always relative to the project root.
- **CLI args**: `main.py` parses `--output-dir` and `--format` via `argparse`, loads config, overrides fields, then passes the config to `MainWindow`. `run.bat` / `run.sh` forward all args via `%*` / `"$@"`.
- **run.bat**: Uses `pythonw.exe` + `start ""` — always launches without a console window, no option to change.
- **Log widget**: `QTextEdit` (not `QPlainTextEdit`) so colored HTML can be appended. Color routing lives in `_log_color(msg)` at module level in `mainWindow.py` — update that function when adding new message types, never inline color logic.
- **Format hint**: A small grey `QLabel` is rendered below the Format/Output bar (`_build_output_bar`) describing each export format. Keep it in sync if formats change.
- **Input sizing**: Use `setMinimumWidth` + `QSizePolicy.Expanding` for any input that displays variable-length content (chapter numbers, paths). Never use `setFixedWidth` for these — it clips large values.

---

## Conventions

- **Imports**: relative inside `app/`, absolute from project root in `main.py` and `tests/`
- **Type hints**: required on all public functions and class attributes
- **Async**: `async def` + `asyncSlot` for Qt-connected coroutines; CPU work goes to `run_in_executor`
- **Naming**: `snake_case` for files, functions, variables; `PascalCase` for classes
- **Commits**: conventional commits — `feat:`, `fix:`, `refactor:`, `docs:`, `test:`
- **No comments** unless the WHY is non-obvious (hidden constraint, workaround, subtle invariant)
- **Qt sizing**: use `setFixedWidth` only for icon buttons (📁, ⚙️). All text inputs and spinboxes use `setMinimumWidth` + `QSizePolicy.Expanding` so they scale with content and window resize.

---

## Config file location

- Windows: `%USERPROFILE%\.mangadl\config.json`
- macOS/Linux: `~/.mangadl/config.json`

---

## Build Status

All 5 phases complete. Ongoing changes tracked via git log.

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Foundation (models, config, utils) | ✅ |
| 2 | Site plugins (base, registry, truyenqqko) | ✅ |
| 3 | Download engine + exporter | ✅ |
| 4 | UI (mainWindow, settingsDialog, main.py) | ✅ |
| 5 | Tests (models, naming, parser) | ✅ |
