# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

`tool_manga_downloader` — Desktop tool for downloading manga from Vietnamese websites for offline reading.

**Stack**: Python 3.10+, PySide6 (Qt6 GUI), aiohttp (async HTTP), BeautifulSoup4 (HTML parsing), qasync (asyncio ↔ Qt bridge)

## Getting Started

```powershell
# Create & activate virtual environment (Windows)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# (Dev tools: testing, linting)
pip install -r requirements-dev.txt

# Run the application (recommended — no console window)
.\run.bat

# Run via bash
bash run.sh

# Run directly (console visible)
python main.py

# CLI options
python main.py --output-dir "D:\Manga" --format cbz

# Run tests
pytest

# Run tests with coverage
pytest --cov=app --cov-report=html

# Lint & format
black app/ tests/
ruff check app/ tests/
mypy app/
```

## Architecture

```
manga_downloader/
├── main.py                     # Entry point: QApplication + qasync event loop + CLI args
├── run.bat                     # Windows launcher (background, no console)
├── run.sh                      # Bash launcher
├── requirements.txt
├── requirements-dev.txt
├── assets/                     # Icons, images
├── output/manga/               # Default download output (gitignored)
├── app/
│   ├── core/
│   │   ├── models.py           # Manga, Chapter dataclasses + Enums
│   │   ├── config.py           # AppConfig dataclass, load/save JSON
│   │   ├── downloader.py       # Async download engine (aiohttp + semaphore)
│   │   └── exporter.py         # Export to CBZ / PDF / EPUB / Folder
│   ├── sites/
│   │   ├── base.py             # BaseSite abstract class
│   │   ├── registry.py         # Plugin registry + get_site_for_url()
│   │   └── truyenqqko.py       # TruyenQQKo site plugin
│   ├── ui/
│   │   ├── mainWindow.py       # Main QMainWindow with all UI widgets
│   │   └── settingsDialog.py   # Settings QDialog
│   └── utils/
│       ├── naming.py           # Zero-padded filenames, sanitize_filename()
│       ├── headers.py          # User-Agent rotation, default headers
│       └── logger.py           # Logging setup
└── tests/
    ├── conftest.py
    ├── fixtures/               # Saved HTML for offline parser tests
    ├── test_models.py
    ├── test_naming.py
    └── test_parser_truyenqqko.py
```

## Key Design Decisions

- **qasync**: The asyncio event loop IS the Qt event loop. All async ops run in the main thread — no threading issues.
- **DownloadSignals**: Plain callback object (not Qt signals) passed into MangaDownloader so it can update UI without depending on Qt.
- **Plugin system**: Each site subclasses `BaseSite`. Add to `SITES` list in `registry.py` to register.
- **Resume**: Before downloading each image, check if file already exists and has size > 0. Skip if so.
- **Output structure**: Images saved to `output/manga/<MangaTitle>/<format>/Chapter_XXXX/001.jpg`. Exported files (CBZ/PDF/EPUB) land in `output/manga/<MangaTitle>/<format>/`.
- **Default output dir**: `[project_root]/output/manga` — resolved via `Path(__file__).parents[2]` in `config.py`.
- **CLI args**: `main.py` accepts `--output-dir` and `--format` to override config at launch time. `run.bat` / `run.sh` forward `%*` / `$@` so args pass through.
- **run.bat**: Uses `pythonw.exe` + `start` so the app always launches without a console window.

## Config file locations

- Windows: `%USERPROFILE%\.mangadl\config.json`
- macOS/Linux: `~/.mangadl/config.json`

## Build Progress

### ✅ Phase 1 — Foundation (DONE)
- [x] CLAUDE.md updated with full plan
- [x] `requirements.txt`
- [x] `requirements-dev.txt`
- [x] `app/core/models.py` — Manga, Chapter, ExportFormat, DownloadStatus
- [x] `app/core/config.py` — AppConfig, load_config(), save_config()
- [x] `app/utils/naming.py` — zero_pad(), sanitize_filename(), image_filename()
- [x] `app/utils/headers.py` — USER_AGENTS list, get_random_ua(), get_default_headers()
- [x] `app/utils/logger.py` — logger singleton

### ✅ Phase 2 — Site plugins (DONE)
- [x] `app/sites/base.py` — BaseSite ABC
- [x] `app/sites/registry.py` — SITES list, get_site_for_url()
- [x] `app/sites/truyenqqko.py` — Full parser with BeautifulSoup

### ✅ Phase 3 — Download engine (DONE)
- [x] `app/core/downloader.py` — MangaDownloader, DownloadSignals, async image fetch
- [x] `app/core/exporter.py` — CBZ, PDF, EPUB, Folder export

### ✅ Phase 4 — UI (DONE)
- [x] `app/ui/settingsDialog.py` — Settings QDialog
- [x] `app/ui/mainWindow.py` — Full main window with all controls
- [x] `main.py` — Entry point with qasync event loop

### ✅ Phase 5 — Tests (DONE)
- [x] `tests/conftest.py` — fixtures: sample_manga_html, sample_chapter_html
- [x] `tests/test_models.py` — Chapter, Manga, enums
- [x] `tests/test_naming.py` — zero_pad, sanitize_filename, chapter_folder_name
- [x] `tests/test_parser_truyenqqko.py` — offline HTML parser tests with mocks
- [x] `pytest.ini` — asyncio_mode = auto

### Status: ✅ COMPLETE — All 5 phases done

## Resume Instructions

If build was interrupted, check "Build Progress" above.
Find the last ✅ completed phase and the first unchecked item in the next phase.
Continue from there — all previous phases' files are already created.
