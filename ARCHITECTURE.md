# Architecture

System layers, data flows, and component responsibilities for `tool_manga_downloader`.

> **Maintenance rule**: Update this file whenever a layer, flow, or component changes. See CLAUDE.md § Documentation Rules.

---

## Layers

```
┌─────────────────────────────────────────────────────┐
│                    Entry Layer                      │
│  main.py — QApplication, qasync loop, CLI args      │
└────────────────────┬────────────────────────────────┘
                     │ creates & passes AppConfig
┌────────────────────▼────────────────────────────────┐
│                     UI Layer                        │
│  app/ui/mainWindow.py     — main window             │
│  app/ui/settingsDialog.py — settings dialog         │
└──────┬──────────────────────────────────┬───────────┘
       │ calls                            │ calls
┌──────▼──────────┐             ┌─────────▼──────────┐
│   Site Plugin   │             │    Core Layer       │
│     Layer       │             │                     │
│ app/sites/      │             │ app/core/           │
│  base.py        │             │  downloader.py      │
│  registry.py    │             │  exporter.py        │
│  truyenqqko.py  │             │  config.py          │
└──────┬──────────┘             │  models.py          │
       │ HTTP                   └─────────┬───────────┘
       ▼                                  │ uses
  External Sites               ┌──────────▼──────────┐
  (truyenqqko.com, …)          │    Utils Layer       │
                                │ app/utils/           │
                                │  naming.py           │
                                │  headers.py          │
                                │  logger.py           │
                                │  history.py          │
                                └──────────┬───────────┘
                                           │ reads/writes
                                ┌──────────▼───────────┐
                                │   Persistence Layer  │
                                │ ~/.mangadl/           │
                                │  config.json          │
                                │  history.json         │
                                └──────────────────────┘
```

---

## Components

### Entry Layer — `main.py`

- Parses CLI args (`--output-dir`, `--format`) via `argparse`
- Loads `AppConfig`, applies CLI overrides
- Creates `QApplication` and `qasync.QEventLoop` (asyncio IS the Qt event loop)
- Instantiates `MainWindow(config=config)` and starts the loop

### UI Layer — `app/ui/`

| File | Responsibility |
|------|---------------|
| `mainWindow.py` | All UI widgets; orchestrates fetch → download → export flow |
| `settingsDialog.py` | Modal dialog for editing `AppConfig`; calls `save_config()` on accept |

**Key UI patterns:**
- Internal Qt signals (`_sig_log`, `_sig_total_progress`, `_sig_chapter_progress`, `_sig_chapter_status`, `_sig_download_finished`) bridge async callbacks to the UI thread safely
- All signal-connected methods have `@Slot(...)` decorators with explicit types
- `QCompleter` on the URL input backed by `QStringListModel` populated from `history.json`; popup triggered on mouse click via `MainWindow.eventFilter` (intercepts `QEvent.Type.MouseButtonPress`), not only on typing
- Log output uses `QTextEdit` (not `QPlainTextEdit`) so colored HTML can be appended; color routing via `_kind_color(kind)` function at module level
- Theme system: `ThemePalette` dataclass holds all theme-specific colours; `_P` is the active palette; `_make_qss()` generates QSS from `_P`; `_apply_theme(name)` rebuilds the central widget after swapping `_P`. Theme toggle button (☀/🌙) in the header saves preference to `config.json`.
- Format/Output bar includes a hint `QLabel` describing each export format
- Spinboxes use `setMinimumWidth` + `QSizePolicy.Expanding` (never `setFixedWidth`)
- `ChapterCard.mark_existing(exists)` shows `ON DISK` badge in gold; re-runs on format/output dir change and after download finishes
- Chapter toolbar has **↓ New** button that checks undownloaded chapters and a `selection_label` showing `X / Y  SELECTED`, auto-updated via `chapter_grid.selection_changed` signal

### Site Plugin Layer — `app/sites/`

| File | Responsibility |
|------|---------------|
| `base.py` | `BaseSite` ABC — defines `matches()`, `parse_manga_info()`, `parse_chapter_images()` |
| `registry.py` | `SITES` list + `get_site_for_url(url)` — instantiates correct plugin or returns `None` |
| `truyenqqko.py` | Concrete plugin for truyenqqko.com — BeautifulSoup HTML parsing |
| `haikyuu.py` | Two plugins: `ReadHaikyuuCom` (read-haikyuu.com, uses WP REST API for images) and `ReadHaikyuOnline` (readhaikyu.online, HTML + Blogger CDN images); shared `_FetchMixin` for aiohttp/cloudscraper |
| `facebook.py` | `FacebookAlbumSite` — downloads photo albums from Facebook pages. Uses Playwright (headless Chromium) to render JS-heavy pages; albums → Chapter list; photos fetched via aiohttp + Playwright session cookies; og:image used for full-res URLs. Requires `pip install playwright && playwright install chromium`. Optional cookies file: `~/.mangadl/fb_cookies.json`. |

To add a new site: subclass `BaseSite`, implement the 3 abstract methods, append the class to `SITES` in `registry.py`.

### Core Layer — `app/core/`

| File | Responsibility |
|------|---------------|
| `models.py` | `Manga`, `Chapter` dataclasses; `ExportFormat`, `DownloadStatus` enums |
| `config.py` | `AppConfig` dataclass; `load_config()` / `save_config()` to `~/.mangadl/config.json` |
| `downloader.py` | `MangaDownloader` — async chapter/image download with semaphore concurrency; `DownloadSignals` callback container |
| `exporter.py` | `export_chapter()` (CBZ, PDF, per-chapter); `export_manga_epub()` (full manga EPUB after all chapters finish) |

### Utils Layer — `app/utils/`

| File | Responsibility |
|------|---------------|
| `naming.py` | `zero_pad()`, `sanitize_filename()`, `chapter_stem()`, `chapter_folder_name()`, `image_filename()` — `chapter_stem(n)` handles decimal chapters: `12.5 → "0012_5"` |
| `headers.py` | `USER_AGENTS` list, `get_random_ua()`, `get_default_headers()`, `get_image_headers()` |
| `logger.py` | Module-level `logger` singleton (Python `logging`) |
| `history.py` | `load_history()` / `save_url()` — URL history in `~/.mangadl/history.json`, max 30 entries, most recent first |
| `manga_io.py` | `save_manga_info(manga, manga_dir)` — serialize `Manga` to `manga_info.json` inside the manga output folder |

### Persistence Layer — `~/.mangadl/`

| File | Written by | Read by |
|------|-----------|---------|
| `config.json` | `save_config()`, Settings dialog | `load_config()` at startup / CLI override |
| `history.json` | `save_url()` after successful fetch | `load_history()` at startup (QCompleter) |
| `output/manga/<Title>/manga_info.json` | `save_manga_info()` after every fetch (create or overwrite) | — (reference only) |

---

## Data Flows

### 1. Fetch Flow

```
User pastes URL → [url_input] → Fetch button
  → fetch_manga() [asyncSlot]
      → get_site_for_url(url)          # registry lookup
      → site.parse_manga_info(url)     # HTTP + BeautifulSoup
      → _populate_manga_info(manga)    # update UI labels/cover
          → _mark_existing_chapters()  # scan disk, highlight ON DISK items
      → save_manga_info(manga, output_dir/MangaTitle/)
          → create folder if not exists
          → write/overwrite manga_info.json (title, url, author, chapters list, fetched_at)
      → save_url(url)                  # persist to history.json
      → _history_model.setStringList() # refresh QCompleter
```

### 2. Download Flow

```
User clicks Download
  → download_selected() [asyncSlot]
      → MangaDownloader.download_manga(manga, chapters, output_dir, format)
          for each chapter:
            → site.parse_chapter_images(chapter.url)   # HTTP + parse
            → _chapter_dir()  → final path (not created yet)
            → temp_dir = final_dir + ".tmp"  (created immediately)
            → _download_images(temp_dir)                # aiohttp + semaphore
                for each image:
                  → skip if file exists and size > 100 bytes  (resume in .tmp)
                  → aiohttp.get(image_url)
                  → write bytes to Chapter_XXXX.tmp/001.jpg
            → export_chapter(temp_dir) [thread pool]    # if format != "folder"
            → temp_dir.rename(final_dir)                # atomic: .tmp → final only on full success
            → emit signals → UI updates (progress bars, chapter status, log)
            # On failure/cancel: .tmp kept for resume next run; final dir never appears partial
            → sleep(delay_seconds)                      # rate limiting
```

### 3. Export Flow

```
Per-chapter (CBZ / PDF):
  chapter_dir/  →  export_chapter()  →  Chapter_XXXX.cbz / .pdf
                                        (in same format/ folder)

Full manga (EPUB — triggered after all chapters done):
  all chapter_dirs/  →  export_manga_epub()  →  MangaTitle.epub
                                                 (in format/ folder)

Folder format:
  no export step — raw images remain in Chapter_XXXX/
```

### 4. Signal Flow (async → UI thread safety)

```
MangaDownloader (async, main thread)
  → DownloadSignals callbacks (lambdas in MainWindow)
      → emit Qt Signal (thread-safe crossing point)
          → @Slot method on MainWindow (UI thread)
              → update widget
```

---

## Output Directory Structure

```
output/manga/                          ← default_output_dir (config.py)
└── <MangaTitle>/
    ├── folder/
    │   └── Chapter_0001/
    │       ├── 001.jpg
    │       └── 002.jpg
    ├── cbz/
    │   ├── Chapter_0001/              ← temp images
    │   ├── Chapter_0001.cbz           ← packed archive
    │   └── Chapter_0012_5.cbz         ← decimal chapter (e.g. 12.5)
    ├── pdf/
    │   ├── Chapter_0001/
    │   └── Chapter_0001.pdf
    └── epub/
        ├── Chapter_0001/
        └── MangaTitle.epub            ← single file covering all chapters
```

---

## Async Model

The asyncio event loop **is** the Qt event loop, bridged by `qasync`. Consequences:

- All coroutines run on the main thread — no threading issues, no locks needed
- `asyncSlot` (from qasync) allows Qt slots to be `async def`
- CPU-bound work (export) uses `loop.run_in_executor(None, fn)` to avoid blocking the UI
- Never call `asyncio.run()` inside the app — use `await` or `asyncio.ensure_future()`
