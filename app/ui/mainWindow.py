from __future__ import annotations
import asyncio
import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QCompleter, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSizePolicy,
    QSpinBox, QSplitter, QStatusBar, QTextEdit, QVBoxLayout, QWidget,
)
from PySide6.QtCore import QEvent, Qt, QStringListModel, QUrl, Signal, Slot
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from qasync import asyncSlot

from app.core.config import AppConfig, load_config, save_config
from app.core.downloader import MangaDownloader, DownloadSignals
from app.core.models import Manga, Chapter, DownloadStatus, ExportFormat
from app.sites.registry import get_site_for_url
from app.utils.logger import logger
from app.utils.history import load_history, save_url as save_history_url
from app.utils.naming import sanitize_filename, chapter_stem
from app.utils.manga_io import save_manga_info

def _log_color(msg: str) -> str:
    if "✓" in msg or "done" in msg.lower() or "finished" in msg.lower() or "saved" in msg.lower():
        return "#4CAF50"   # green — success
    if "✗" in msg or "failed" in msg.lower() or "error" in msg.lower():
        return "#F44336"   # red — error
    if "⚠" in msg or "warning" in msg.lower() or "cancelled" in msg.lower():
        return "#FF9800"   # orange — warning
    if "Downloading" in msg:
        return "#64B5F6"   # light blue — in progress
    if "Fetching" in msg or "Fetched" in msg:
        return "#B0BEC5"   # grey-blue — info
    return "#E0E0E0"       # default light grey


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
        self._on_disk = False
        self.setFlags(self.flags() | Qt.ItemIsUserCheckable)
        self.setCheckState(Qt.Checked)
        self._refresh_text()

    def set_status(self, status: DownloadStatus) -> None:
        self.chapter.status = status
        self._refresh_text()

    def mark_existing(self, exists: bool) -> None:
        self._on_disk = exists
        self._refresh_text()

    def _refresh_text(self) -> None:
        icon = _STATUS_ICON.get(self.chapter.status, "")
        badge = "  ⚠ ON DISK" if self._on_disk else ""
        self.setText(f"{self.chapter.title}{badge}  {icon}")


class MainWindow(QMainWindow):
    # Internal signal to safely update UI from async context
    _sig_log = Signal(str)
    _sig_total_progress = Signal(int, int)
    _sig_chapter_progress = Signal(int, int)
    _sig_chapter_status = Signal(object, str)  # chapter id(obj), status value
    _sig_download_finished = Signal()

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        super().__init__()
        self.config: AppConfig = config if config is not None else load_config()
        self.manga: Optional[Manga] = None
        self.downloader: Optional[MangaDownloader] = None
        self._chapter_items: dict[int, ChapterItem] = {}  # id(chapter) → item
        self._last_selected: list[Chapter] = []
        self._nam = QNetworkAccessManager(self)
        self._history_model = QStringListModel(load_history(), self)

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

        self._url_completer = QCompleter(self._history_model, self)
        self._url_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._url_completer.setFilterMode(Qt.MatchContains)
        self._url_completer.setCompletionMode(QCompleter.PopupCompletion)
        self.url_input.setCompleter(self._url_completer)
        self.url_input.installEventFilter(self)

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
        info_col.setSpacing(3)

        self.title_label = QLabel("—")
        self.title_label.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.title_label.setWordWrap(True)

        self.author_label = QLabel("✍️  —")
        self.chapter_count_label = QLabel("📑 —")
        self.site_label = QLabel("🌐 —")

        self.url_label = QLabel("🔗 —")
        self.url_label.setStyleSheet("color: #888; font-size: 11px;")
        self.url_label.setWordWrap(True)
        self.url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.desc_edit = QTextEdit()
        self.desc_edit.setReadOnly(True)
        self.desc_edit.setMaximumHeight(70)
        self.desc_edit.setPlaceholderText("No description")
        self.desc_edit.setStyleSheet("font-size: 12px; background: transparent; border: none;")

        info_col.addWidget(self.title_label)
        info_col.addWidget(self.author_label)
        info_col.addWidget(self.chapter_count_label)
        info_col.addWidget(self.site_label)
        info_col.addWidget(self.url_label)
        info_col.addWidget(self.desc_edit)

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
        self.select_new_btn = QPushButton("↓ New")
        self.select_new_btn.setToolTip("Select only chapters not yet downloaded")
        toolbar.addWidget(self.select_all_btn)
        toolbar.addWidget(self.select_none_btn)
        toolbar.addWidget(self.select_new_btn)
        toolbar.addWidget(QLabel("Range:"))
        self.range_from = QSpinBox()
        self.range_from.setMinimum(1)
        self.range_from.setMinimumWidth(80)
        self.range_from.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.range_to = QSpinBox()
        self.range_to.setMinimum(1)
        self.range_to.setMinimumWidth(80)
        self.range_to.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.range_apply_btn = QPushButton("Apply")
        self.range_apply_btn.setFixedWidth(60)
        toolbar.addWidget(self.range_from)
        toolbar.addWidget(QLabel("to"))
        toolbar.addWidget(self.range_to)
        toolbar.addWidget(self.range_apply_btn)
        toolbar.addStretch()
        self.selection_label = QLabel("0 / 0 selected")
        self.selection_label.setStyleSheet("color: gray; font-size: 11px;")
        toolbar.addWidget(self.selection_label)

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
        self.format_combo.setCurrentIndex(2)  # PDF default
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
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.document().setMaximumBlockCount(500)
        self.log_view.setStyleSheet("font-family: monospace; font-size: 12px;")
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
        self.select_new_btn.clicked.connect(self._select_new)
        self.range_apply_btn.clicked.connect(self._apply_range)
        self.chapter_list.itemChanged.connect(self._update_selection_label)
        self.url_input.returnPressed.connect(self._on_fetch_clicked)
        self.format_combo.currentIndexChanged.connect(self._mark_existing_chapters)
        self.output_dir_input.editingFinished.connect(self._mark_existing_chapters)

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

    def eventFilter(self, obj: object, event: QEvent) -> bool:
        if obj is self.url_input and event.type() == QEvent.Type.MouseButtonPress:
            self._url_completer.setCompletionPrefix(self.url_input.text())
            self._url_completer.complete()
        return super().eventFilter(obj, event)

    # ─── button handlers ─────────────────────────────────────────────────────

    @asyncSlot()
    async def _on_fetch_clicked(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            return

        if not url.startswith(("http://", "https://")):
            self._log("⚠ Invalid URL — must start with http:// or https://")
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

            manga_dir = Path(self.output_dir_input.text()) / sanitize_filename(manga.title)
            info_path = save_manga_info(manga, manga_dir)
            self._log(f"Saved manga info → {info_path}")

            updated = save_history_url(url)
            self._history_model.setStringList(updated)

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

        self._last_selected = selected
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

    def _select_new(self) -> None:
        for i in range(self.chapter_list.count()):
            item: ChapterItem = self.chapter_list.item(i)  # type: ignore[assignment]
            state = Qt.Unchecked if item._on_disk else Qt.Checked
            item.setCheckState(state)

    def _update_selection_label(self) -> None:
        total = self.chapter_list.count()
        checked = sum(
            1 for i in range(total)
            if self.chapter_list.item(i).checkState() == Qt.Checked
        )
        self.selection_label.setText(f"{checked} / {total} selected")

    def _apply_range(self) -> None:
        lo = self.range_from.value()
        hi = self.range_to.value()
        if lo > hi:
            lo, hi = hi, lo
        for i in range(self.chapter_list.count()):
            item: ChapterItem = self.chapter_list.item(i)  # type: ignore[assignment]
            n = item.chapter.number
            state = Qt.Checked if lo <= n <= hi else Qt.Unchecked
            item.setCheckState(state)

    # ─── populate manga info ─────────────────────────────────────────────────

    def _populate_manga_info(self, manga: Manga) -> None:
        self.title_label.setText(manga.title)
        self.author_label.setText(f"✍️  {manga.author or 'Unknown'}")
        self.chapter_count_label.setText(f"📑 {len(manga.chapters)} chapters")
        self.site_label.setText(f"🌐 {manga.site_name}")
        self.url_label.setText(f"🔗 {manga.url}")
        self.desc_edit.setPlainText(manga.description or "")

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
        self._mark_existing_chapters()
        self._update_selection_label()

        if manga.cover_url:
            self._load_cover(manga.cover_url, manga.url)

    def _mark_existing_chapters(self) -> None:
        if not self.manga:
            return
        output_dir = Path(self.output_dir_input.text())
        fmt = self.format_combo.currentData()
        manga_dir = output_dir / sanitize_filename(self.manga.title) / fmt
        for i in range(self.chapter_list.count()):
            item: ChapterItem = self.chapter_list.item(i)  # type: ignore[assignment]
            chapter_dir = manga_dir / f"Chapter_{chapter_stem(item.chapter.number)}"
            exists = chapter_dir.is_dir() and any(chapter_dir.iterdir())
            item.mark_existing(exists)

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

    @Slot(str)
    def _append_log(self, msg: str) -> None:
        color = _log_color(msg)
        escaped = msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.log_view.append(f'<span style="color:{color};">{escaped}</span>')

    @Slot(int, int)
    def _update_total_progress(self, done: int, total: int) -> None:
        self.total_progress.setRange(0, total)
        self.total_progress.setValue(done)

    @Slot(int, int)
    def _update_chapter_progress(self, done: int, total: int) -> None:
        self.chapter_progress.setRange(0, total)
        self.chapter_progress.setValue(done)

    def _update_chapter_status_slot(self, chapter_id: int, status_value: str) -> None:
        item = self._chapter_items.get(chapter_id)
        if item:
            item.set_status(DownloadStatus(status_value))

    @Slot()
    def _on_download_finished_slot(self) -> None:
        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._mark_existing_chapters()

        failed = [c for c in self._last_selected if c.status == DownloadStatus.FAILED]
        done = [c for c in self._last_selected if c.status == DownloadStatus.DONE]
        total = len(self._last_selected)

        self._log("─" * 40)
        if not failed:
            self._log(f"✓ Download finished — {done}/{total} chapters completed.")
        else:
            self._log(f"✗ Download finished — {len(failed)}/{total} chapters FAILED:")
            for ch in failed:
                self._log(f"  ✗ {ch.title}")
            self._log("─" * 40)

            msg = QMessageBox(self)
            msg.setWindowTitle("Download Errors")
            msg.setIcon(QMessageBox.Warning)
            msg.setText(f"{len(failed)} chapter(s) failed to download.")
            details = "\n".join(f"• {ch.title}" for ch in failed)
            msg.setDetailedText(details)
            msg.exec()

    def _log(self, msg: str) -> None:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._append_log(f"[{ts}] {msg}")
