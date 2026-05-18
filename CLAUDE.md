# CLAUDE.md

Rules and context for Claude Code when working in this repository.

---

## Context

`tool_manga_downloader` — PySide6 desktop app that downloads manga from Vietnamese websites for offline reading.

**Stack**: Python 3.10+, PySide6 (Qt6 GUI), aiohttp (async HTTP), BeautifulSoup4 (HTML parsing), qasync (asyncio ↔ Qt bridge)

---

## Git Rules

- **Never commit or push unless the user explicitly asks.** Make all code/doc changes freely, but only run `git add` / `git commit` / `git push` when the user says to.

---

## Pre-task Rule

Before making any code change, **read `ARCHITECTURE.md` first**. This ensures every change is consistent with the existing layers, flows, and component boundaries.

---

## Documentation Rules

After every change that affects behavior, structure, or conventions:

- **CLAUDE.md**: update Architecture, Key Design Decisions, or Conventions to reflect the change. Add a new rule if a decision was made that Claude should remember for future sessions.
- **ARCHITECTURE.md**: update the affected layer, component table, or data flow diagram. This is the primary reference for system structure — keep it accurate at all times.
- **README.md**: update any user-facing section that the change affects — install steps, usage, output structure, config, hotkeys, etc. Skip if the change is purely internal (refactor, implementation detail with no visible effect), check need to update if update code affects change UI

When in doubt: if a future Claude or a new contributor would be confused without the update, update it.

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
│   │   ├── truyenqqko.py       # TruyenQQKo site plugin
│   │   └── haikyuu.py          # ReadHaikyuuCom + ReadHaikyuOnline plugins
│   ├── ui/
│   │   ├── mainWindow.py       # QMainWindow; accepts optional AppConfig via __init__(config=)
│   │   └── settingsDialog.py   # Settings QDialog
│   └── utils/
│       ├── naming.py           # zero_pad(), sanitize_filename(), chapter_stem(), image_filename()
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
- **Output structure**: `<output_dir>/<MangaTitle>/<format>/Chapter_XXXX/001.jpg`. The format subfolder (`cbz`, `pdf`, `epub`, `folder`) is always present. Decimal chapters use `_` separator: chapter 12.5 → `Chapter_0012_5`.
- **chapter_stem()**: Always use `chapter_stem(number)` from `naming.py` to build the folder/file name for a chapter — never `int(chapter.number)` or inline formatting. This handles decimal chapters (12.5 → `0012_5`) correctly.
- **PDF export**: Uses Pillow's native `save_all` PDF writer — no `img2pdf` dependency, no 14400-unit page size limit. Blank white end page is appended via Pillow `Image.new`.
- **Default output dir**: Resolved at import time via `Path(__file__).parents[2] / "output" / "manga"` in `config.py` — always relative to the project root.
- **CLI args**: `main.py` parses `--output-dir` and `--format` via `argparse`, loads config, overrides fields, then passes the config to `MainWindow`. `run.bat` / `run.sh` forward all args via `%*` / `"$@"`.
- **run.bat**: Uses `pythonw.exe` + `start ""` — always launches without a console window, no option to change.
- **Log widget**: `QTextEdit` (not `QPlainTextEdit`) so colored HTML can be appended. Color routing lives in `_log_color(msg)` at module level in `mainWindow.py` — update that function when adding new message types, never inline color logic.
- **Format hint**: A small grey `QLabel` is rendered below the Format/Output bar (`_build_output_bar`) describing each export format. Keep it in sync if formats change.
- **Input sizing**: Use `setMinimumWidth` + `QSizePolicy.Expanding` for any input that displays variable-length content (chapter numbers, paths). Never use `setFixedWidth` for these — it clips large values.
- **URL completer on click**: The URL input uses an `eventFilter` on `MainWindow` to intercept `QEvent.Type.MouseButtonPress` and call `completer.complete()` — this shows the history popup immediately on click, not only when typing.
- **ON DISK badge**: `_mark_existing_chapters()` must be called after every event that changes on-disk state: populate, format/output dir change, and download finished. Badge shows `⚠ ON DISK` text only — no color change on the item.
- **Selection count label**: `selection_label` in the chapter toolbar shows `X / Y selected`. Updated via `itemChanged` signal on `chapter_list` — no manual refresh needed in select/range helpers.

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
