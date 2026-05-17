from __future__ import annotations
import asyncio
import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QPlainTextEdit, QProgressBar, QPushButton, QSizePolicy,
    QSpinBox, QSplitter, QStatusBar, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt, QUrl, Signal, QObject
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from qasync import asyncSlot

from app.core.config import AppConfig, load_config, save_config
from app.core.downloader import MangaDownloader, DownloadSignals
from app.core.models import Manga, Chapter, DownloadStatus, ExportFormat
from app.sites.registry import get_site_for_url
from app.utils.logger import logger

_STATUS_ICON = {
    DownloadStatus.PENDING: "⌛",
    DownloadStatus.DOWNLOADING: "⏳",
    DownloadStatus.DONE: "✅",
    DownloadStatus.FAILED: "❌",
    DownloadStatus.SKIPPED: "⏭",
}


class ChapterItem(QListWidgetItem):
    def __init__(self, chapter: Chapter) -> None:
        super().__init__()
        self.chapter = chapter
        self.setFlags(self.flags() | Qt.ItemIsUserCheckable)
        self.setCheckState(Qt.Checked)
        self._refresh_text()

    def set_status(self, status: DownloadStatus) -> None:
        self.chapter.status = status
        self._refresh_text()

    def _refresh_text(self) -> None:
        icon = _STATUS_ICON.get(self.chapter.status, "")
        self.setText(f"{self.chapter.title}  {icon}")


class MainWindow(QMainWindow):
    # Internal signal to safely update UI from async context
    _sig_log = Signal(str)
    _sig_total_progress = Signal(int, int)
    _sig_chapter_progress = Signal(int, int)
    _sig_chapter_status = Signal(int, str)   # chapter id(obj), status value
    _sig_download_finished = Signal()

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        super().__init__()
        self.config: AppConfig = config if config is not None else load_config()
        self.manga: Optional[Manga] = None
        self.downloader: Optional[MangaDownloader] = None
        self._chapter_items: dict[int, ChapterItem] = {}  # id(chapter) → item
        self._nam = QNetworkAccessManager(self)

        self._build_ui()
        self._connect_signals()
        self._apply_shortcuts()

    # ─── UI construction ─────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setWindowTitle("Manga Downloader")
        self.setMinimumSize(820, 680)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(6)

        root.addLayout(self._build_url_bar())
        root.addWidget(self._build_info_panel())
        root.addWidget(self._build_chapter_section())
        root.addLayout(self._build_output_bar())
        root.addWidget(self._build_progress_section())
        root.addWidget(self._build_log_section())

        self.setStatusBar(QStatusBar())

    def _build_url_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste manga URL here…  (e.g. https://truyenqqko.com/truyen-tranh/...)")
        self.fetch_btn = QPushButton("🔍 Fetch")
        self.fetch_btn.setFixedWidth(90)
        row.addWidget(QLabel("URL:"))
        row.addWidget(self.url_input)
        row.addWidget(self.fetch_btn)
        return row

    def _build_info_panel(self) -> QGroupBox:
        box = QGroupBox("Manga Info")
        row = QHBoxLayout(box)

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(120, 160)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setStyleSheet("border: 1px solid #555; background: #222;")
        self.cover_label.setText("No cover")

        info_col = QVBoxLayout()
        self.title_label = QLabel("—")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.title_label.setWordWrap(True)
        self.author_label = QLabel("Author: —")
        self.chapter_count_label = QLabel("Chapters: —")
        self.site_label = QLabel("Site: —")

        info_col.addWidget(self.title_label)
        info_col.addWidget(self.author_label)
        info_col.addWidget(self.chapter_count_label)
        info_col.addWidget(self.site_label)
        info_col.addStretch()

        row.addWidget(self.cover_label)
        row.addLayout(info_col)
        return box

    def _build_chapter_section(self) -> QGroupBox:
        box = QGroupBox("Chapters")
        col = QVBoxLayout(box)

        # Toolbar row: select all / none / range
        toolbar = QHBoxLayout()
        self.select_all_btn = QPushButton("✓ All")
        self.select_none_btn = QPushButton("✗ None")
        toolbar.addWidget(self.select_all_btn)
        toolbar.addWidget(self.select_none_btn)
        toolbar.addWidget(QLabel("Range:"))
        self.range_from = QSpinBox()
        self.range_from.setMinimum(1)
        self.range_from.setFixedWidth(70)
        self.range_to = QSpinBox()
        self.range_to.setMinimum(1)
        self.range_to.setFixedWidth(70)
        self.range_apply_btn = QPushButton("Apply")
        self.range_apply_btn.setFixedWidth(60)
        toolbar.addWidget(self.range_from)
        toolbar.addWidget(QLabel("to"))
        toolbar.addWidget(self.range_to)
        toolbar.addWidget(self.range_apply_btn)
        toolbar.addStretch()

        self.chapter_list = QListWidget()
        self.chapter_list.setAlternatingRowColors(True)

        col.addLayout(toolbar)
        col.addWidget(self.chapter_list)
        return box

    def _build_output_bar(self) -> QVBoxLayout:
        col = QVBoxLayout()

        row = QHBoxLayout()
        row.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        for fmt in ExportFormat:
            self.format_combo.addItem(fmt.value.upper(), fmt.value)
        self.format_combo.setCurrentIndex(1)  # CBZ default
        row.addWidget(self.format_combo)

        row.addWidget(QLabel("Output:"))
        self.output_dir_input = QLineEdit(self.config.default_output_dir)
        row.addWidget(self.output_dir_input)

        self.browse_btn = QPushButton("📁")
        self.browse_btn.setFixedWidth(36)
        row.addWidget(self.browse_btn)

        self.download_btn = QPushButton("⬇️ Download")
        self.download_btn.setEnabled(False)
        row.addWidget(self.download_btn)

        self.cancel_btn = QPushButton("⏹ Cancel")
        self.cancel_btn.setEnabled(False)
        row.addWidget(self.cancel_btn)

        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.setFixedWidth(36)
        row.addWidget(self.settings_btn)

        col.addLayout(row)

        hint = QLabel(
            "CBZ: comic archive (compatible with most readers)  •  "
            "PDF: single PDF file  •  "
            "EPUB: e-book format  •  "
            "Folder: raw images only"
        )
        hint.setStyleSheet("color: gray; font-size: 11px;")
        col.addWidget(hint)

        return col

    def _build_progress_section(self) -> QGroupBox:
        box = QGroupBox("Progress")
        col = QVBoxLayout(box)

        self.total_progress = QProgressBar()
        self.total_progress.setFormat("Total: %v/%m chapters")
        self.total_progress.setTextVisible(True)

        self.chapter_progress = QProgressBar()
        self.chapter_progress.setFormat("Chapter: %v/%m images")
        self.chapter_progress.setTextVisible(True)

        col.addWidget(self.total_progress)
        col.addWidget(self.chapter_progress)
        return box

    def _build_log_section(self) -> QGroupBox:
        box = QGroupBox("Log")
        box.setMaximumHeight(180)
        col = QVBoxLayout(box)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        col.addWidget(self.log_view)
        return box

    # ─── signals & shortcuts ─────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self.fetch_btn.clicked.connect(self._on_fetch_clicked)
        self.download_btn.clicked.connect(self._on_download_clicked)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        self.browse_btn.clicked.connect(self._on_browse_clicked)
        self.settings_btn.clicked.connect(self._on_settings_clicked)
        self.select_all_btn.clicked.connect(self._select_all)
        self.select_none_btn.clicked.connect(self._select_none)
        self.range_apply_btn.clicked.connect(self._apply_range)
        self.url_input.returnPressed.connect(self._on_fetch_clicked)

        # Internal async → UI signals
        self._sig_log.connect(self._append_log)
        self._sig_total_progress.connect(self._update_total_progress)
        self._sig_chapter_progress.connect(self._update_chapter_progress)
        self._sig_chapter_status.connect(self._update_chapter_status_slot)
        self._sig_download_finished.connect(self._on_download_finished_slot)

    def _apply_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+A"), self, self._select_all)
        QShortcut(QKeySequence("Ctrl+D"), self, self._on_download_clicked)
        QShortcut(QKeySequence("Escape"), self, self._on_cancel_clicked)
        QShortcut(QKeySequence("Ctrl+,"), self, self._on_settings_clicked)
        QShortcut(QKeySequence("Return"), self, self._on_fetch_clicked)

    # ─── button handlers ─────────────────────────────────────────────────────

    @asyncSlot()
    async def _on_fetch_clicked(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            return

        self.fetch_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.chapter_list.clear()
        self._chapter_items.clear()
        self._log(f"Fetching: {url}")

        try:
            site = get_site_for_url(url)
            if not site:
                self._log("⚠ No plugin found for this URL. Supported: truyenqqko.com")
                return

            manga = await site.parse_manga_info(url)
            self.manga = manga
            self._populate_manga_info(manga)
            self._log(f"Fetched {len(manga.chapters)} chapters: {manga.title}")

        except Exception as e:
            self._log(f"Error fetching manga: {e}")
            logger.error("Fetch error", exc_info=True)
        finally:
            self.fetch_btn.setEnabled(True)

    @asyncSlot()
    async def _on_download_clicked(self) -> None:
        if not self.manga:
            return

        selected = [
            self.chapter_list.item(i).chapter  # type: ignore[union-attr]
            for i in range(self.chapter_list.count())
            if self.chapter_list.item(i).checkState() == Qt.Checked  # type: ignore[union-attr]
        ]
        if not selected:
            self._log("No chapters selected.")
            return

        output_dir = Path(self.output_dir_input.text().strip() or self.config.default_output_dir)
        export_format = self.format_combo.currentData()

        self.download_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.total_progress.setRange(0, len(selected))
        self.total_progress.setValue(0)
        self.chapter_progress.setValue(0)

        signals = DownloadSignals()
        signals.on_log = self._sig_log.emit
        signals.on_total_progress = self._sig_total_progress.emit
        signals.on_chapter_progress = self._sig_chapter_progress.emit
        signals.on_chapter_status = lambda cid, st: self._sig_chapter_status.emit(cid, st.value)
        signals.on_finished = self._sig_download_finished.emit

        self.downloader = MangaDownloader(self.config, signals)
        await self.downloader.download_manga(self.manga, selected, output_dir, export_format)

        # EPUB: assemble after all chapters done
        if export_format == "epub":
            try:
                from app.core.exporter import export_manga_epub
                manga_dir = output_dir / __import__("app.utils.naming", fromlist=["sanitize_filename"]).sanitize_filename(self.manga.title)
                done_chapters = [c for c in selected if c.status == DownloadStatus.DONE]
                if done_chapters:
                    from app.utils.naming import sanitize_filename
                    manga_dir = output_dir / sanitize_filename(self.manga.title)
                    epub_path = await asyncio.get_event_loop().run_in_executor(
                        None, export_manga_epub, manga_dir, self.manga.title, done_chapters
                    )
                    self._log(f"EPUB saved: {epub_path}")
            except Exception as e:
                self._log(f"EPUB export failed: {e}")

    def _on_cancel_clicked(self) -> None:
        if self.downloader:
            self.downloader.cancel()

    def _on_browse_clicked(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select output folder", self.output_dir_input.text())
        if folder:
            self.output_dir_input.setText(folder)

    def _on_settings_clicked(self) -> None:
        from app.ui.settingsDialog import SettingsDialog
        dlg = SettingsDialog(self.config, parent=self)
        dlg.exec()

    # ─── chapter list controls ───────────────────────────────────────────────

    def _select_all(self) -> None:
        for i in range(self.chapter_list.count()):
            self.chapter_list.item(i).setCheckState(Qt.Checked)

    def _select_none(self) -> None:
        for i in range(self.chapter_list.count()):
            self.chapter_list.item(i).setCheckState(Qt.Unchecked)

    def _apply_range(self) -> None:
        lo = self.range_from.value()
        hi = self.range_to.value()
        if lo > hi:
            lo, hi = hi, lo
        for i in range(self.chapter_list.count()):
            item: ChapterItem = self.chapter_list.item(i)  # type: ignore[assignment]
            n = int(item.chapter.number)
            state = Qt.Checked if lo <= n <= hi else Qt.Unchecked
            item.setCheckState(state)

    # ─── populate manga info ─────────────────────────────────────────────────

    def _populate_manga_info(self, manga: Manga) -> None:
        self.title_label.setText(manga.title)
        self.author_label.setText(f"✍️  {manga.author or 'Unknown'}")
        self.chapter_count_label.setText(f"📑 {len(manga.chapters)} chapters")
        self.site_label.setText(f"🌐 {manga.site_name}")

        self.chapter_list.clear()
        self._chapter_items.clear()
        max_n = max((c.number for c in manga.chapters), default=1) or 1
        self.range_from.setRange(1, int(max_n))
        self.range_to.setRange(1, int(max_n))
        self.range_to.setValue(int(max_n))

        for chapter in manga.chapters:
            item = ChapterItem(chapter)
            self.chapter_list.addItem(item)
            self._chapter_items[id(chapter)] = item

        self.download_btn.setEnabled(True)

        if manga.cover_url:
            self._load_cover(manga.cover_url, manga.url)

    def _load_cover(self, cover_url: str, referer: str) -> None:
        req = QNetworkRequest(QUrl(cover_url))
        req.setRawHeader(b"Referer", referer.encode())
        req.setRawHeader(b"User-Agent", b"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        reply = self._nam.get(req)
        reply.finished.connect(lambda: self._on_cover_reply(reply))

    def _on_cover_reply(self, reply: QNetworkReply) -> None:
        if reply.error() == QNetworkReply.NoError:
            pixmap = QPixmap()
            pixmap.loadFromData(reply.readAll())
            if not pixmap.isNull():
                self.cover_label.setPixmap(
                    pixmap.scaled(120, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
        reply.deleteLater()

    # ─── progress / log slots (called from Qt signals → safe on UI thread) ───

    def _append_log(self, msg: str) -> None:
        self.log_view.appendPlainText(msg)

    def _update_total_progress(self, done: int, total: int) -> None:
        self.total_progress.setRange(0, total)
        self.total_progress.setValue(done)

    def _update_chapter_progress(self, done: int, total: int) -> None:
        self.chapter_progress.setRange(0, total)
        self.chapter_progress.setValue(done)

    def _update_chapter_status_slot(self, chapter_id: int, status_value: str) -> None:
        item = self._chapter_items.get(chapter_id)
        if item:
            item.set_status(DownloadStatus(status_value))

    def _on_download_finished_slot(self) -> None:
        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._log("Download finished.")

    def _log(self, msg: str) -> None:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"[{ts}] {msg}")
