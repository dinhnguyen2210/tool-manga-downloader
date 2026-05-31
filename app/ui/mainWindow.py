from __future__ import annotations
import asyncio
import datetime
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QButtonGroup, QCompleter, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSpinBox,
    QStatusBar, QTextEdit, QVBoxLayout, QWidget,
)
from PySide6.QtCore import QEvent, QRect, Qt, QStringListModel, QUrl, Signal, Slot
from PySide6.QtGui import (
    QColor, QFont, QKeySequence, QPainter, QPen, QPixmap, QShortcut,
)
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

# ─── Accent constants (theme-invariant) ───────────────────────────────────────
VERM       = "#FF3A1A"
VERM_DEEP  = "#c5260e"
JADE       = "#2dd4a4"
GOLD       = "#ffc83d"
ON_ACCENT  = "#100604"


# ─── Theme Palette ────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ThemePalette:
    name:         str
    BG_DEEP:      str
    INK:          str
    INK_DIM:      str
    INK_FAINT:    str
    PAPER:        str
    PAPER_2:      str
    PAPER_3:      str
    LINE:         str
    LINE_SOFT:    str
    TITLEA:       str
    SCROLL_HOVER: str   # scrollbar handle :hover
    CARD_HOVER:   str   # format card :hover bg
    CARD_CHECKED: str   # format card :checked bg


DARK_PALETTE = ThemePalette(
    name         = "dark",
    BG_DEEP      = "#0a0908",
    INK          = "#f5f3ef",
    INK_DIM      = "#c8c2b8",
    INK_FAINT    = "#8a8277",
    PAPER        = "#141210",
    PAPER_2      = "#1a1815",
    PAPER_3      = "#201e1b",
    LINE         = "#302d29",
    LINE_SOFT    = "#272420",
    TITLEA       = "#181613",
    SCROLL_HOVER = "#3a3632",
    CARD_HOVER   = "#252220",
    CARD_CHECKED = "#2a1510",
)

LIGHT_PALETTE = ThemePalette(
    name         = "light",
    BG_DEEP      = "#f4f1ec",
    INK          = "#1a1612",
    INK_DIM      = "#3a3530",
    INK_FAINT    = "#6a6560",
    PAPER        = "#ffffff",
    PAPER_2      = "#ede9e3",
    PAPER_3      = "#e4e0d9",
    LINE         = "#c4c0ba",
    LINE_SOFT    = "#d8d4cd",
    TITLEA       = "#e0dcd6",
    SCROLL_HOVER = "#b0acaa",
    CARD_HOVER   = "#d8d4cd",
    CARD_CHECKED = "#ffdad4",
)

# Active palette — updated before every UI build
_P: ThemePalette = DARK_PALETTE


# ─── System theme detection ───────────────────────────────────────────────────
def _detect_system_theme() -> str:
    """Returns 'dark' or 'light' from Windows registry; falls back to 'dark'."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return "light" if val == 1 else "dark"
    except Exception:
        return "dark"


# ─── QSS generator ────────────────────────────────────────────────────────────
def _make_qss() -> str:
    p = _P
    return f"""
QMainWindow, QWidget {{
    background: {p.BG_DEEP};
    color: {p.INK};
    font-size: 13px;
}}
QScrollArea, QScrollArea > QWidget > QWidget {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent; width: 8px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {p.LINE}; border-radius: 4px; min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: {p.SCROLL_HOVER}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent; height: 8px;
}}
QScrollBar::handle:horizontal {{
    background: {p.LINE}; border-radius: 4px; min-width: 20px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QLineEdit {{
    background: {p.PAPER_2};
    border: 1px solid {p.LINE_SOFT};
    border-radius: 8px;
    padding: 0 14px;
    color: {p.INK};
    font-size: 13px;
    selection-background-color: {VERM};
    selection-color: {ON_ACCENT};
}}
QLineEdit:focus {{ border-color: {VERM}; background: {p.PAPER_3}; }}
QLineEdit#url_input {{
    font-family: "Courier New", monospace;
    font-size: 12px;
    min-height: 44px;
}}
QComboBox {{
    background: {p.PAPER_2}; border: 1px solid {p.LINE_SOFT}; border-radius: 6px;
    padding: 5px 10px 5px 12px; color: {p.INK}; font-size: 13px; min-height: 32px;
}}
QComboBox:focus {{ border-color: {VERM}; }}
QComboBox::drop-down {{
    subcontrol-origin: border; subcontrol-position: center right;
    width: 22px; border-left: 1px solid {p.LINE_SOFT};
    border-top-right-radius: 6px; border-bottom-right-radius: 6px;
    background: {p.PAPER_3};
}}
QComboBox::drop-down:hover {{ background: {p.LINE}; }}
QComboBox::down-arrow {{ width: 8px; height: 8px; }}
QComboBox QAbstractItemView {{
    background: {p.PAPER_3}; border: 1px solid {p.LINE};
    selection-background-color: {VERM}; selection-color: {ON_ACCENT}; outline: none;
}}
QAbstractSpinBox {{
    background: {p.PAPER_2}; border: 1px solid {p.LINE_SOFT}; border-radius: 5px;
    padding: 4px 6px 4px 8px; color: {p.INK}; font-family: "Courier New", monospace;
    font-size: 11px; min-height: 32px; min-width: 68px;
}}
QAbstractSpinBox:focus {{ border-color: {VERM}; }}
QAbstractSpinBox::up-button {{
    subcontrol-origin: border; subcontrol-position: top right;
    width: 20px; border-left: 1px solid {p.LINE_SOFT};
    border-top-right-radius: 5px; background: {p.PAPER_3};
}}
QAbstractSpinBox::up-button:hover {{ background: {p.LINE}; }}
QAbstractSpinBox::up-button:pressed {{ background: {p.LINE_SOFT}; }}
QAbstractSpinBox::down-button {{
    subcontrol-origin: border; subcontrol-position: bottom right;
    width: 20px; border-left: 1px solid {p.LINE_SOFT};
    border-bottom-right-radius: 5px; background: {p.PAPER_3};
}}
QAbstractSpinBox::down-button:hover {{ background: {p.LINE}; }}
QAbstractSpinBox::down-button:pressed {{ background: {p.LINE_SOFT}; }}
QAbstractSpinBox::up-arrow {{ width: 8px; height: 8px; }}
QAbstractSpinBox::down-arrow {{ width: 8px; height: 8px; }}
QPushButton {{
    background: {p.PAPER_2}; border: 1px solid {p.LINE_SOFT}; border-radius: 8px;
    padding: 6px 16px; color: {p.INK_DIM}; font-size: 13px;
}}
QPushButton:hover {{
    background: {p.PAPER_3}; border-color: {p.LINE}; color: {p.INK};
}}
QPushButton:pressed {{ background: {p.CARD_HOVER}; }}
QPushButton:disabled {{ color: {p.LINE}; border-color: {p.LINE_SOFT}; }}
QPushButton#fetch_btn {{
    background: {VERM}; border: none; color: {ON_ACCENT};
    font-weight: 600; min-height: 44px; padding: 0 22px; border-radius: 8px;
}}
QPushButton#fetch_btn:hover {{ background: #ff5234; }}
QPushButton#fetch_btn:pressed {{ background: {VERM_DEEP}; }}
QPushButton#fetch_btn:disabled {{
    background: {p.PAPER_3}; color: {p.INK_FAINT}; border: 1px solid {p.LINE_SOFT};
}}
QPushButton#download_btn {{
    background: {VERM}; border: none; color: {ON_ACCENT};
    font-weight: 700; font-size: 13px; min-height: 38px;
    padding: 0 22px; border-radius: 6px;
}}
QPushButton#download_btn:hover {{ background: #ff5234; }}
QPushButton#download_btn:pressed {{ background: {VERM_DEEP}; }}
QPushButton#download_btn:disabled {{
    background: {p.PAPER_3}; color: {p.LINE}; border: 1px solid {p.LINE_SOFT};
}}
QPushButton#cancel_btn {{
    background: {p.PAPER_2}; border: 1px solid {VERM};
    color: {VERM}; font-weight: 600; min-height: 38px;
    padding: 0 22px; border-radius: 6px;
}}
QPushButton#cancel_btn:hover {{ background: {p.CARD_CHECKED}; color: #ff5234; }}
QPushButton#cancel_btn:disabled {{ border-color: {p.LINE_SOFT}; color: {p.LINE}; }}
QPushButton#small_btn {{
    background: {p.PAPER_2}; border: 1px solid {p.LINE_SOFT}; border-radius: 5px;
    padding: 3px 10px; color: {p.INK_DIM}; font-size: 11px; min-height: 26px;
}}
QPushButton#small_btn:hover {{ background: {p.PAPER_3}; color: {p.INK}; }}
QPushButton#small_btn:disabled {{ color: {p.LINE}; }}
QPushButton#small_btn_accent {{
    background: {p.CARD_CHECKED}; border: 1px solid {VERM}; border-radius: 5px;
    padding: 3px 10px; color: {VERM}; font-size: 11px; min-height: 26px;
}}
QPushButton#small_btn_accent:hover {{ background: {p.CARD_HOVER}; }}
QPushButton#small_btn_accent:disabled {{ color: {p.LINE}; border-color: {p.LINE_SOFT}; }}
QPushButton#icon_btn {{
    background: {p.PAPER_2}; border: 1px solid {p.LINE_SOFT};
    border-radius: 6px; color: {p.INK_DIM}; min-height: 38px; padding: 0;
}}
QPushButton#icon_btn:hover {{ background: {p.PAPER_3}; color: {p.INK}; border-color: {p.LINE}; }}
QTextEdit {{
    background: {p.PAPER}; border: none; color: {p.INK_DIM};
    font-family: "Courier New", monospace; font-size: 11px;
    selection-background-color: {VERM}; selection-color: {ON_ACCENT};
}}
QProgressBar {{
    background: {p.PAPER_3}; border: none; border-radius: 3px;
    height: 5px; text-align: center; color: {p.INK_FAINT}; font-size: 10px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {VERM_DEEP}, stop:1 {VERM});
    border-radius: 3px;
}}
QLabel {{ background: transparent; color: {p.INK_DIM}; }}
QStatusBar {{
    background: {p.BG_DEEP}; border-top: 1px solid {p.LINE_SOFT};
    color: {p.INK_FAINT}; font-size: 11px;
}}
QToolTip {{
    background: {p.PAPER_3}; border: 1px solid {p.LINE};
    color: {p.INK}; padding: 4px 8px; border-radius: 4px; font-size: 12px;
}}
QMessageBox {{ background: {p.PAPER}; }}
QMessageBox QPushButton {{ min-width: 70px; }}
"""


# ─── Log kind detection ───────────────────────────────────────────────────────
def _log_kind(msg: str) -> str:
    if "✓" in msg or "done" in msg.lower() or "finished" in msg.lower() or "saved" in msg.lower():
        return "ok"
    if "✗" in msg or "failed" in msg.lower() or "error" in msg.lower():
        return "err"
    if "⚠" in msg or "warning" in msg.lower() or "cancelled" in msg.lower():
        return "warn"
    return "info"


def _kind_color(kind: str) -> str:
    return {"ok": JADE, "err": VERM, "warn": GOLD}.get(kind, _P.INK_FAINT)


_STATUS_ICON = {
    DownloadStatus.PENDING:     "",
    DownloadStatus.DOWNLOADING: "",
    DownloadStatus.DONE:        "✓",
    DownloadStatus.FAILED:      "✗",
    DownloadStatus.SKIPPED:     "⏭",
}


# ─── Progress Ring ────────────────────────────────────────────────────────────
class ProgressRingWidget(QWidget):
    def __init__(self, size: int = 96, parent=None) -> None:
        super().__init__(parent)
        self._value: float = 0.0
        self._sz = size
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def setValue(self, v: float) -> None:
        self._value = max(0.0, min(100.0, v))
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = self._sz
        m = 7
        arc_rect = QRect(m, m, s - 2 * m, s - 2 * m)

        pen = QPen(QColor(_P.PAPER_3), 6)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(arc_rect, 90 * 16, -360 * 16)

        if self._value > 0:
            pen2 = QPen(QColor(VERM), 6)
            pen2.setCapStyle(Qt.RoundCap)
            p.setPen(pen2)
            p.drawArc(arc_rect, 90 * 16, int(-self._value / 100 * 360 * 16))

        font = QFont()
        font.setPixelSize(20)
        font.setWeight(QFont.Light)
        p.setFont(font)
        p.setPen(QColor(_P.INK))
        p.drawText(QRect(0, s // 2 - 14, s, 26), Qt.AlignCenter, f"{int(self._value)}%")

        font2 = QFont()
        font2.setPixelSize(8)
        font2.setFamily("Courier New")
        p.setFont(font2)
        p.setPen(QColor(_P.INK_FAINT))
        p.drawText(QRect(0, s // 2 + 12, s, 14), Qt.AlignCenter, "OVERALL")

        p.end()


# ─── Chapter Card ─────────────────────────────────────────────────────────────
class ChapterCard(QFrame):
    selection_changed = Signal()

    def __init__(self, chapter: Chapter, parent=None) -> None:
        super().__init__(parent)
        self.chapter = chapter
        self._selected: bool = True
        self._on_disk: bool = False
        self._status: DownloadStatus = DownloadStatus.PENDING
        self._progress: int = 0
        self._build()
        self._refresh()

    def _build(self) -> None:
        self.setFixedHeight(40)
        self.setCursor(Qt.PointingHandCursor)

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 5, 10, 5)
        row.setSpacing(6)

        n = self.chapter.number
        num_str = f"#{int(n):03d}" if n == int(n) else f"#{n}"
        self._num = QLabel(num_str)
        self._num.setFixedWidth(42)
        font_mono = QFont("Courier New")
        font_mono.setPixelSize(11)
        self._num.setFont(font_mono)

        self._title = QLabel(self.chapter.title)
        self._title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._title.setStyleSheet(f"font-size: 12px; color: {_P.INK};")

        self._badge = QLabel("")
        self._badge.setFixedWidth(36)
        self._badge.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        font_badge = QFont("Courier New")
        font_badge.setPixelSize(10)
        self._badge.setFont(font_badge)

        row.addWidget(self._num)
        row.addWidget(self._title)
        row.addWidget(self._badge)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self._selected = not self._selected
            self._refresh()
            self.selection_changed.emit()

    def set_selected(self, v: bool) -> None:
        self._selected = v
        self._refresh()

    def is_selected(self) -> bool:
        return self._selected

    def mark_existing(self, exists: bool) -> None:
        self._on_disk = exists
        self._refresh()

    def set_status(self, status: DownloadStatus) -> None:
        self._status = status
        self._refresh()

    def set_progress(self, pct: int) -> None:
        self._progress = pct
        self.update()

    def _refresh(self) -> None:
        if self._status == DownloadStatus.DONE:
            self._badge.setText("✓")
            self._badge.setStyleSheet(f"color: {JADE}; font-size: 12px;")
        elif self._status == DownloadStatus.FAILED:
            self._badge.setText("✗")
            self._badge.setStyleSheet(f"color: {VERM}; font-size: 12px;")
        elif self._status == DownloadStatus.DOWNLOADING:
            self._badge.setText(f"{self._progress}%")
            self._badge.setStyleSheet(f"color: {VERM}; font-size: 10px;")
        elif self._on_disk:
            self._badge.setText("ON DISK")
            self._badge.setStyleSheet(f"color: {GOLD}; font-size: 9px;")
        else:
            self._badge.setText("")

        num_color = VERM if self._selected else _P.INK_FAINT
        self._num.setStyleSheet(
            f"font-family: 'Courier New', monospace; font-size: 11px; color: {num_color};"
        )
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(0, 0, -1, -1)

        if self._selected:
            p.fillRect(r, QColor(_P.CARD_CHECKED))
        else:
            p.fillRect(r, QColor(_P.PAPER_2))

        if self._status == DownloadStatus.DOWNLOADING and self._progress > 0:
            c = QColor(VERM)
            c.setAlpha(45)
            fill = QRect(r.x(), r.y(), int(r.width() * self._progress / 100), r.height())
            p.fillRect(fill, c)
        elif self._status == DownloadStatus.DONE:
            c = QColor(JADE)
            c.setAlpha(22)
            p.fillRect(r, c)

        border_color = VERM if self._selected else _P.LINE_SOFT
        pen = QPen(QColor(border_color), 1)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, 6, 6)

        p.end()


# ─── Chapter Grid ─────────────────────────────────────────────────────────────
class ChapterGridWidget(QScrollArea):
    selection_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cards: list[ChapterCard] = []
        self._card_map: dict[int, ChapterCard] = {}

        self._container = QWidget()
        self._grid = QGridLayout(self._container)
        self._grid.setSpacing(6)
        self._grid.setContentsMargins(0, 0, 4, 0)

        self.setWidget(self._container)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setMinimumHeight(180)
        self.setMaximumHeight(240)

    def clear(self) -> None:
        for card in self._cards:
            card.deleteLater()
        self._cards.clear()
        self._card_map.clear()

    def add_chapter(self, chapter: Chapter) -> ChapterCard:
        card = ChapterCard(chapter)
        card.selection_changed.connect(self._on_card_changed)
        row, col = divmod(len(self._cards), 3)
        self._grid.addWidget(card, row, col)
        self._cards.append(card)
        self._card_map[id(chapter)] = card
        return card

    def _on_card_changed(self) -> None:
        self.selection_changed.emit()

    def count(self) -> int:
        return len(self._cards)

    def selected_count(self) -> int:
        return sum(1 for c in self._cards if c.is_selected())

    def get_selected_chapters(self) -> list[Chapter]:
        return [c.chapter for c in self._cards if c.is_selected()]

    def select_all(self) -> None:
        for c in self._cards:
            c.set_selected(True)
        self.selection_changed.emit()

    def select_none(self) -> None:
        for c in self._cards:
            c.set_selected(False)
        self.selection_changed.emit()

    def select_new(self) -> None:
        for c in self._cards:
            c.set_selected(not c._on_disk)
        self.selection_changed.emit()

    def select_range(self, lo: float, hi: float) -> None:
        for c in self._cards:
            n = c.chapter.number
            c.set_selected(lo <= n <= hi)
        self.selection_changed.emit()

    def update_status(self, chapter_id: int, status: DownloadStatus) -> None:
        card = self._card_map.get(chapter_id)
        if card:
            card.set_status(status)

    def mark_chapter_existing(self, chapter_id: int, exists: bool) -> None:
        card = self._card_map.get(chapter_id)
        if card:
            card.mark_existing(exists)


# ─── Main Window ──────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    _sig_log                = Signal(str)
    _sig_total_progress     = Signal(int, int)
    _sig_chapter_progress   = Signal(int, int)
    _sig_chapter_status     = Signal(object, str)
    _sig_download_finished  = Signal()

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        super().__init__()
        self.config: AppConfig = config if config is not None else load_config()
        self.manga: Optional[Manga] = None
        self.downloader: Optional[MangaDownloader] = None
        self._last_selected: list[Chapter] = []
        self._nam = QNetworkAccessManager(self)
        self._history_model = QStringListModel(load_history(), self)

        # Resolve and apply initial palette
        global _P
        effective = (
            _detect_system_theme() if self.config.theme == "system"
            else self.config.theme
        )
        _P = LIGHT_PALETTE if effective == "light" else DARK_PALETTE

        self._build_ui()
        self._connect_signals()
        self._apply_shortcuts()

    # ─── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setWindowTitle("Tachi — Manga Downloader")
        self.setMinimumSize(920, 720)
        self.setStyleSheet(_make_qss())

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        root.addWidget(self._build_header())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(8)
        content_layout.setContentsMargins(18, 14, 18, 8)

        content_layout.addLayout(self._build_url_bar())
        content_layout.addWidget(self._build_info_panel())
        content_layout.addWidget(self._build_chapter_section())

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        root.addWidget(self._build_progress_dash())

        self.setStatusBar(QStatusBar())

    def _build_header(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(38)
        bar.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {_P.TITLEA}, stop:1 {_P.PAPER});
                border-bottom: 1px solid {_P.LINE_SOFT};
            }}
            QLabel {{ color: {_P.INK_DIM}; background: transparent; }}
            QPushButton {{
                background: transparent; border: none;
                color: {_P.INK_FAINT}; font-size: 12px; padding: 0 2px;
            }}
            QPushButton:hover {{ color: {_P.INK}; }}
        """)
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 0, 14, 0)
        row.setSpacing(0)

        logo_box = QWidget()
        logo_box.setFixedSize(22, 22)
        logo_box.setStyleSheet(f"background: {VERM}; border-radius: 5px;")
        logo_layout = QHBoxLayout(logo_box)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_lbl = QLabel("⬡")
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setStyleSheet(f"color: {ON_ACCENT}; font-size: 11px;")
        logo_layout.addWidget(logo_lbl)

        title_lbl = QLabel("Tachi")
        title_lbl.setStyleSheet(
            f"color: {_P.INK}; font-size: 17px; font-style: italic; margin-left: 8px;"
        )
        ver_lbl = QLabel("v2.5")
        ver_lbl.setStyleSheet(
            f"color: {_P.INK_FAINT}; font-family: 'Courier New',monospace; font-size: 10px;"
            f" margin-left: 6px; letter-spacing: 1px;"
        )

        row.addWidget(logo_box)
        row.addWidget(title_lbl)
        row.addWidget(ver_lbl)
        row.addSpacing(24)

        for menu_item in ["File", "Library", "Sources", "View", "Help"]:
            btn = QPushButton(menu_item)
            btn.setFixedHeight(38)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; border: none; color: {_P.INK_FAINT};
                    font-size: 12px; padding: 0 10px;
                }}
                QPushButton:hover {{ color: {_P.INK}; }}
            """)
            row.addWidget(btn)

        row.addStretch()

        dot = QLabel("●")
        dot.setStyleSheet(f"color: {JADE}; font-size: 8px;")
        src_lbl = QLabel("14 sources online")
        src_lbl.setStyleSheet(
            f"color: {_P.INK_FAINT}; font-family: 'Courier New',monospace; font-size: 11px;"
        )
        row.addWidget(dot)
        row.addSpacing(4)
        row.addWidget(src_lbl)
        row.addSpacing(14)

        # Theme toggle: ☀ = currently dark (click → light), 🌙 = currently light (click → dark)
        theme_icon = "☀" if _P.name == "dark" else "🌙"
        theme_tip  = "Switch to light mode" if _P.name == "dark" else "Switch to dark mode"
        self._theme_btn = QPushButton(theme_icon)
        self._theme_btn.setFixedSize(28, 28)
        self._theme_btn.setToolTip(theme_tip)
        self._theme_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none; color: {_P.INK_FAINT};
                font-size: 14px;
            }}
            QPushButton:hover {{ color: {_P.INK}; }}
        """)
        row.addWidget(self._theme_btn)
        row.addSpacing(4)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(28, 28)
        self.settings_btn.setToolTip("Settings  (Ctrl+,)")
        self.settings_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none; color: {_P.INK_FAINT};
                font-size: 16px;
            }}
            QPushButton:hover {{ color: {_P.INK}; }}
        """)
        row.addWidget(self.settings_btn)

        return bar

    def _build_url_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        pill = QWidget()
        pill.setStyleSheet(f"""
            QWidget {{
                background: {_P.PAPER_2};
                border: 1px solid {_P.LINE_SOFT};
                border-radius: 8px;
            }}
        """)
        pill.setMinimumHeight(44)
        pill_row = QHBoxLayout(pill)
        pill_row.setContentsMargins(14, 0, 14, 0)
        pill_row.setSpacing(10)

        tag = QLabel("URL")
        tag.setStyleSheet(
            f"color: {_P.INK_FAINT}; font-family: 'Courier New',monospace;"
            f" font-size: 10px; letter-spacing: 1px;"
        )
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background: {_P.LINE_SOFT}; border: none;")

        self.url_input = QLineEdit()
        self.url_input.setObjectName("url_input")
        self.url_input.setPlaceholderText("https://truyenqqko.com/truyen-tranh/…")
        self.url_input.setStyleSheet(
            f"background: transparent; border: none; border-radius: 0;"
            f" color: {_P.INK}; font-family: 'Courier New',monospace; font-size: 12px;"
        )

        self._url_completer = QCompleter(self._history_model, self)
        self._url_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._url_completer.setFilterMode(Qt.MatchContains)
        self._url_completer.setCompletionMode(QCompleter.PopupCompletion)
        self.url_input.setCompleter(self._url_completer)
        self.url_input.installEventFilter(self)

        self._valid_badge = QLabel("✓ valid")
        self._valid_badge.setStyleSheet(
            f"color: {JADE}; font-family: 'Courier New',monospace; font-size: 11px;"
        )
        self._valid_badge.setVisible(False)

        pill_row.addWidget(tag)
        pill_row.addWidget(sep)
        pill_row.addWidget(self.url_input)
        pill_row.addWidget(self._valid_badge)

        self.fetch_btn = QPushButton("🔍  Fetch")
        self.fetch_btn.setObjectName("fetch_btn")
        self.fetch_btn.setFixedHeight(44)
        self.fetch_btn.setMinimumWidth(100)

        refresh_btn = QPushButton("↺")
        refresh_btn.setObjectName("icon_btn")
        refresh_btn.setFixedSize(44, 44)
        refresh_btn.setToolTip("Clear")
        refresh_btn.clicked.connect(self._clear_url)

        row.addWidget(pill, 1)
        row.addWidget(self.fetch_btn)
        row.addWidget(refresh_btn)
        return row

    def _build_info_panel(self) -> QFrame:
        panel = QFrame()
        panel.setStyleSheet(f"""
            QFrame {{
                background: {_P.PAPER_2};
                border: 1px solid {_P.LINE_SOFT};
                border-radius: 10px;
            }}
            QLabel {{ background: transparent; }}
        """)
        outer = QHBoxLayout(panel)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(18)

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(120, 160)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setStyleSheet(
            f"border: 1px solid {_P.LINE_SOFT}; background: {_P.PAPER_3}; border-radius: 6px;"
            f" color: {_P.INK_FAINT}; font-size: 11px; font-family: 'Courier New',monospace;"
        )
        self.cover_label.setText("NO COVER")

        meta_col = QVBoxLayout()
        meta_col.setSpacing(6)

        self.title_label = QLabel("—")
        self.title_label.setStyleSheet(
            f"font-size: 22px; font-weight: 600; color: {_P.INK}; font-style: italic;"
        )
        self.title_label.setWordWrap(True)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(
            f"color: {_P.INK_FAINT}; font-family: 'Courier New',monospace; font-size: 11px;"
        )

        grid_widget = QWidget()
        grid_widget.setStyleSheet("background: transparent;")
        self._meta_grid = QGridLayout(grid_widget)
        self._meta_grid.setSpacing(0)
        self._meta_grid.setContentsMargins(0, 4, 0, 4)

        self.author_val   = self._make_meta_row(0, "AUTHOR",   "✍", "—")
        self.site_val     = self._make_meta_row(0, "SOURCE",   "🌐", "—", col=2)
        self.chapters_val = self._make_meta_row(1, "CHAPTERS", "📑", "—")
        self.status_val   = self._make_meta_row(1, "STATUS",   "●", "—", col=2)

        self._chips_widget = QWidget()
        self._chips_widget.setStyleSheet("background: transparent;")
        self._chips_row = QHBoxLayout(self._chips_widget)
        self._chips_row.setContentsMargins(0, 0, 0, 0)
        self._chips_row.setSpacing(6)
        self._chips_row.addStretch()

        self.desc_edit = QTextEdit()
        self.desc_edit.setReadOnly(True)
        self.desc_edit.setMaximumHeight(56)
        self.desc_edit.setPlaceholderText("No description")
        self.desc_edit.setStyleSheet(
            f"font-size: 12px; font-style: italic; color: {_P.INK_FAINT};"
            f" background: transparent; border: none;"
        )

        meta_col.addWidget(self.title_label)
        meta_col.addWidget(self.stats_label)
        meta_col.addWidget(grid_widget)
        meta_col.addWidget(self._chips_widget)
        meta_col.addWidget(self.desc_edit)

        outer.addWidget(self.cover_label)
        outer.addLayout(meta_col)
        return panel

    def _make_meta_row(
        self, row: int, label: str, icon: str, default: str, col: int = 0
    ) -> QLabel:
        lbl = QLabel(f"{icon}  {label}")
        lbl.setStyleSheet(
            f"color: {_P.INK_FAINT}; font-family: 'Courier New',monospace;"
            f" font-size: 9px; letter-spacing: 1px; padding: 4px 0;"
        )
        val = QLabel(default)
        val.setStyleSheet(f"color: {_P.INK}; font-size: 12px; padding: 4px 0;")
        self._meta_grid.addWidget(lbl, row, col)
        self._meta_grid.addWidget(val, row, col + 1)
        return val

    def _build_chapter_section(self) -> QFrame:
        panel = QFrame()
        panel.setStyleSheet(f"""
            QFrame {{
                background: {_P.PAPER_2};
                border: 1px solid {_P.LINE_SOFT};
                border-radius: 10px;
            }}
            QLabel {{ background: transparent; }}
        """)
        col = QVBoxLayout(panel)
        col.setContentsMargins(18, 14, 18, 0)
        col.setSpacing(10)

        hdr = QHBoxLayout()
        ch_title = QLabel("Chapters")
        ch_title.setStyleSheet(f"font-size: 17px; font-style: italic; color: {_P.INK};")
        self.selection_label = QLabel("AWAITING")
        self.selection_label.setStyleSheet(
            f"color: {_P.INK_FAINT}; font-family: 'Courier New',monospace; font-size: 10px; letter-spacing: 1px;"
        )
        hdr.addWidget(ch_title)
        hdr.addWidget(self.selection_label)
        hdr.addStretch()

        filter_pill = QWidget()
        filter_pill.setStyleSheet(
            f"background: {_P.PAPER_3}; border: 1px solid {_P.LINE_SOFT}; border-radius: 6px;"
        )
        filter_row = QHBoxLayout(filter_pill)
        filter_row.setContentsMargins(8, 0, 8, 0)
        filter_row.setSpacing(6)
        search_icon = QLabel("🔍")
        search_icon.setStyleSheet(f"color: {_P.INK_FAINT}; font-size: 11px;")
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter…")
        self.filter_input.setFixedWidth(140)
        self.filter_input.setFixedHeight(28)
        self.filter_input.setStyleSheet(
            f"background: transparent; border: none; color: {_P.INK};"
            f" font-size: 11px; border-radius: 0;"
        )
        filter_row.addWidget(search_icon)
        filter_row.addWidget(self.filter_input)
        hdr.addWidget(filter_pill)
        col.addLayout(hdr)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self.select_all_btn  = self._small_btn("✓  All")
        self.select_none_btn = self._small_btn("✗  None")
        self.select_new_btn  = self._small_btn("↓  New", accent=True)
        self.select_new_btn.setToolTip("Select only chapters not yet on disk")

        toolbar.addWidget(self.select_all_btn)
        toolbar.addWidget(self.select_none_btn)
        toolbar.addWidget(self.select_new_btn)

        div = QFrame()
        div.setFrameShape(QFrame.VLine)
        div.setFixedWidth(1)
        div.setStyleSheet(f"background: {_P.LINE_SOFT}; border: none;")
        toolbar.addWidget(div)

        range_lbl = QLabel("RANGE")
        range_lbl.setStyleSheet(
            f"color: {_P.INK_FAINT}; font-family: 'Courier New',monospace; font-size: 10px; letter-spacing: 1px;"
        )
        self.range_from = QSpinBox()
        self.range_from.setMinimum(1)
        self.range_from.setMinimumWidth(64)
        self.range_from.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        dash_lbl = QLabel("—")
        dash_lbl.setStyleSheet(f"color: {_P.INK_FAINT};")
        self.range_to = QSpinBox()
        self.range_to.setMinimum(1)
        self.range_to.setMinimumWidth(64)
        self.range_to.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.range_apply_btn = self._small_btn("Apply")
        self.range_apply_btn.setFixedWidth(60)

        toolbar.addWidget(range_lbl)
        toolbar.addWidget(self.range_from)
        toolbar.addWidget(dash_lbl)
        toolbar.addWidget(self.range_to)
        toolbar.addWidget(self.range_apply_btn)
        toolbar.addStretch()
        col.addLayout(toolbar)

        hdiv = QFrame()
        hdiv.setFrameShape(QFrame.HLine)
        hdiv.setStyleSheet(f"background: {_P.LINE_SOFT}; border: none; max-height: 1px;")
        col.addWidget(hdiv)

        self.chapter_grid = ChapterGridWidget()
        col.addWidget(self.chapter_grid)

        col.addWidget(self._build_format_output_block())

        return panel

    def _small_btn(self, text: str, accent: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("small_btn_accent" if accent else "small_btn")
        return btn

    def _build_format_output_block(self) -> QWidget:
        block = QWidget()
        block.setStyleSheet("background: transparent;")
        outer = QVBoxLayout(block)
        outer.setContentsMargins(0, 8, 0, 14)
        outer.setSpacing(10)

        hdiv = QFrame()
        hdiv.setFrameShape(QFrame.HLine)
        hdiv.setStyleSheet(f"background: {_P.LINE_SOFT}; border: none; max-height: 1px;")
        outer.addWidget(hdiv)

        fmt_lbl = QLabel("OUTPUT FORMAT")
        fmt_lbl.setStyleSheet(
            f"color: {_P.INK_FAINT}; font-family: 'Courier New',monospace;"
            f" font-size: 9px; letter-spacing: 1.4px;"
        )
        outer.addWidget(fmt_lbl)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(6)
        # Clean up old group if rebuilding
        if hasattr(self, "_format_group") and self._format_group:
            self._format_group.deleteLater()
        self._format_group = QButtonGroup(block)
        self._format_group.setExclusive(True)
        _fmt_defs = [
            ("pdf",    "PDF",  "single bound file"),
            ("cbz",    "CBZ",  "comic archive"),
            ("epub",   "EPUB", "reflowable e-book"),
            ("folder", "RAW",  "image folders"),
        ]
        self._format_btns: dict[str, QPushButton] = {}
        for key, label, desc in _fmt_defs:
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setProperty("fmt_key", key)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setMinimumHeight(52)

            btn_layout = QVBoxLayout(btn)
            btn_layout.setContentsMargins(8, 6, 8, 6)
            btn_layout.setSpacing(2)
            lbl_top = QLabel(label)
            lbl_top.setStyleSheet(
                f"font-size: 15px; font-style: italic; color: {_P.INK}; background: transparent; border: none;"
            )
            lbl_top.setAttribute(Qt.WA_TransparentForMouseEvents)
            lbl_bot = QLabel(desc)
            lbl_bot.setStyleSheet(
                f"font-size: 9px; color: {_P.INK_FAINT}; background: transparent; border: none; letter-spacing: .3px;"
            )
            lbl_bot.setAttribute(Qt.WA_TransparentForMouseEvents)
            btn_layout.addWidget(lbl_top)
            btn_layout.addWidget(lbl_bot)

            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {_P.PAPER_3};
                    border: 1px solid {_P.LINE_SOFT};
                    border-radius: 6px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background: {_P.CARD_HOVER};
                    border-color: {_P.LINE};
                }}
                QPushButton:checked {{
                    background: {_P.CARD_CHECKED};
                    border-color: {VERM};
                }}
            """)

            self._format_group.addButton(btn)
            self._format_btns[key] = btn
            cards_row.addWidget(btn)
            if key == "pdf":
                btn.setChecked(True)

        outer.addLayout(cards_row)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        path_pill = QWidget()
        path_pill.setStyleSheet(
            f"background: {_P.PAPER_3}; border: 1px solid {_P.LINE_SOFT}; border-radius: 6px;"
        )
        path_pill.setMinimumHeight(38)
        path_inner = QHBoxLayout(path_pill)
        path_inner.setContentsMargins(10, 0, 4, 0)
        path_inner.setSpacing(8)

        folder_icon = QLabel("📁")
        folder_icon.setStyleSheet(f"color: {_P.INK_FAINT}; font-size: 13px;")
        save_lbl = QLabel("SAVE TO")
        save_lbl.setStyleSheet(
            f"color: {_P.INK_FAINT}; font-family: 'Courier New',monospace; font-size: 9px; letter-spacing: 1px;"
        )
        vdiv = QFrame()
        vdiv.setFrameShape(QFrame.VLine)
        vdiv.setFixedWidth(1)
        vdiv.setStyleSheet(f"background: {_P.LINE_SOFT}; border: none;")

        self.output_dir_input = QLineEdit(self.config.default_output_dir)
        self.output_dir_input.setStyleSheet(
            f"background: transparent; border: none; border-radius: 0;"
            f" color: {_P.INK_DIM}; font-family: 'Courier New',monospace; font-size: 11px;"
        )
        self.output_dir_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.output_dir_input.setMinimumWidth(200)

        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none; color: {_P.INK_FAINT};
                font-size: 11px; padding: 4px 8px;
            }}
            QPushButton:hover {{ color: {_P.INK}; }}
        """)

        path_inner.addWidget(folder_icon)
        path_inner.addWidget(save_lbl)
        path_inner.addWidget(vdiv)
        path_inner.addWidget(self.output_dir_input)
        path_inner.addWidget(self.browse_btn)

        self.download_btn = QPushButton("⬇  Download")
        self.download_btn.setObjectName("download_btn")
        self.download_btn.setEnabled(False)
        self.download_btn.setMinimumWidth(130)

        self.cancel_btn = QPushButton("⏹  Cancel")
        self.cancel_btn.setObjectName("cancel_btn")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setMinimumWidth(100)

        bottom_row.addWidget(path_pill, 1)
        bottom_row.addWidget(self.download_btn)
        bottom_row.addWidget(self.cancel_btn)
        outer.addLayout(bottom_row)

        return block

    def _build_progress_dash(self) -> QWidget:
        dash = QWidget()
        dash.setFixedHeight(168)
        dash.setStyleSheet(
            f"background: {_P.PAPER_2}; border-top: 1px solid {_P.LINE_SOFT};"
        )
        row = QHBoxLayout(dash)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        # ── Left: ring + ETA ──────────────────────────────────────────────────
        left = QWidget()
        left.setFixedWidth(240)
        left.setStyleSheet(f"border-right: 1px solid {_P.LINE_SOFT}; background: transparent;")
        left_col = QVBoxLayout(left)
        left_col.setContentsMargins(16, 12, 16, 12)
        left_col.setSpacing(6)

        prog_hdr = QHBoxLayout()
        prog_hdr_lbl = QLabel("PROGRESS")
        prog_hdr_lbl.setStyleSheet(
            f"color: {_P.INK_FAINT}; font-family:'Courier New',monospace; font-size: 10px; letter-spacing:1.4px;"
        )
        self._active_dot = QLabel("● IDLE")
        self._active_dot.setStyleSheet(
            f"color: {_P.INK_FAINT}; font-family:'Courier New',monospace; font-size: 10px;"
        )
        prog_hdr.addWidget(prog_hdr_lbl)
        prog_hdr.addStretch()
        prog_hdr.addWidget(self._active_dot)
        left_col.addLayout(prog_hdr)

        ring_row = QHBoxLayout()
        self.progress_ring = ProgressRingWidget(size=96)
        self._chapters_done_lbl = QLabel("0\n/0")
        self._chapters_done_lbl.setStyleSheet(
            f"color: {_P.INK}; font-size: 20px; font-style: italic;"
        )
        self._eta_lbl = QLabel("ETA  --:--")
        self._eta_lbl.setStyleSheet(
            f"color: {_P.INK_DIM}; font-family:'Courier New',monospace; font-size: 10px;"
        )
        right_of_ring = QVBoxLayout()
        right_of_ring.addWidget(self._chapters_done_lbl)
        right_of_ring.addWidget(self._eta_lbl)
        right_of_ring.addStretch()
        ring_row.addWidget(self.progress_ring)
        ring_row.addSpacing(10)
        ring_row.addLayout(right_of_ring)
        ring_row.addStretch()
        left_col.addLayout(ring_row)
        left_col.addStretch()

        # ── Middle: current chapter + progress bars ───────────────────────────
        mid = QWidget()
        mid.setStyleSheet(f"border-right: 1px solid {_P.LINE_SOFT}; background: transparent;")
        mid_col = QVBoxLayout(mid)
        mid_col.setContentsMargins(16, 12, 16, 12)
        mid_col.setSpacing(8)

        now_hdr = QHBoxLayout()
        now_lbl = QLabel("NOW DOWNLOADING")
        now_lbl.setStyleSheet(
            f"color: {_P.INK_FAINT}; font-family:'Courier New',monospace; font-size: 10px; letter-spacing:1.4px;"
        )
        self._speed_lbl = QLabel("SPEED  —")
        self._speed_lbl.setStyleSheet(
            f"color: {_P.INK_DIM}; font-family:'Courier New',monospace; font-size: 10px;"
        )
        now_hdr.addWidget(now_lbl)
        now_hdr.addStretch()
        now_hdr.addWidget(self._speed_lbl)
        mid_col.addLayout(now_hdr)

        self._current_chapter_lbl = QLabel("—")
        self._current_chapter_lbl.setStyleSheet(
            f"color: {_P.INK}; font-size: 13px; font-style: italic;"
        )
        mid_col.addWidget(self._current_chapter_lbl)

        total_lbl = QLabel("TOTAL")
        total_lbl.setStyleSheet(
            f"color: {_P.INK_FAINT}; font-family:'Courier New',monospace; font-size: 9px; letter-spacing:1px;"
        )
        self.total_progress = QProgressBar()
        self.total_progress.setFormat("%v / %m chapters")
        self.total_progress.setTextVisible(True)
        self.total_progress.setFixedHeight(14)
        self.total_progress.setStyleSheet(
            f"QProgressBar {{ background:{_P.PAPER_3}; border:none; border-radius:3px;"
            f" text-align:center; color:{_P.INK_FAINT}; font-size:10px; height:14px;}}"
            f"QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f" stop:0 {VERM_DEEP}, stop:1 {VERM}); border-radius:3px; }}"
        )
        mid_col.addWidget(total_lbl)
        mid_col.addWidget(self.total_progress)

        chap_lbl = QLabel("CHAPTER")
        chap_lbl.setStyleSheet(
            f"color: {_P.INK_FAINT}; font-family:'Courier New',monospace; font-size: 9px; letter-spacing:1px;"
        )
        self.chapter_progress = QProgressBar()
        self.chapter_progress.setFormat("%v / %m images")
        self.chapter_progress.setTextVisible(True)
        self.chapter_progress.setFixedHeight(14)
        self.chapter_progress.setStyleSheet(
            f"QProgressBar {{ background:{_P.PAPER_3}; border:none; border-radius:3px;"
            f" text-align:center; color:{_P.INK_FAINT}; font-size:10px; height:14px;}}"
            f"QProgressBar::chunk {{ background: {JADE}; border-radius:3px; }}"
        )
        mid_col.addWidget(chap_lbl)
        mid_col.addWidget(self.chapter_progress)
        mid_col.addStretch()

        # ── Right: log ────────────────────────────────────────────────────────
        right = QWidget()
        right.setFixedWidth(320)
        right.setStyleSheet("background: transparent;")
        right_col = QVBoxLayout(right)
        right_col.setContentsMargins(14, 12, 14, 12)
        right_col.setSpacing(6)

        log_hdr = QHBoxLayout()
        log_lbl = QLabel("LOG")
        log_lbl.setStyleSheet(
            f"color: {_P.INK_FAINT}; font-family:'Courier New',monospace; font-size: 10px; letter-spacing:1.4px;"
        )
        live_lbl = QLabel("tail · live")
        live_lbl.setStyleSheet(
            f"color: {_P.INK_FAINT}; font-family:'Courier New',monospace; font-size: 9px;"
        )
        log_hdr.addWidget(log_lbl)
        log_hdr.addStretch()
        log_hdr.addWidget(live_lbl)
        right_col.addLayout(log_hdr)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.document().setMaximumBlockCount(300)
        right_col.addWidget(self.log_view)

        row.addWidget(left)
        row.addWidget(mid, 1)
        row.addWidget(right)
        return dash

    # ─── signals & shortcuts ──────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self.fetch_btn.clicked.connect(self._on_fetch_clicked)
        self.download_btn.clicked.connect(self._on_download_clicked)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        self.browse_btn.clicked.connect(self._on_browse_clicked)
        self.settings_btn.clicked.connect(self._on_settings_clicked)
        self._theme_btn.clicked.connect(self._on_theme_toggle)
        self.select_all_btn.clicked.connect(self._select_all)
        self.select_none_btn.clicked.connect(self._select_none)
        self.select_new_btn.clicked.connect(self._select_new)
        self.range_apply_btn.clicked.connect(self._apply_range)
        self.chapter_grid.selection_changed.connect(self._update_selection_label)
        self.url_input.returnPressed.connect(self._on_fetch_clicked)
        self.output_dir_input.editingFinished.connect(self._mark_existing_chapters)
        self._format_group.buttonClicked.connect(lambda _: self._mark_existing_chapters())
        self.filter_input.textChanged.connect(self._on_filter_changed)

        self._sig_log.connect(self._append_log)
        self._sig_total_progress.connect(self._update_total_progress)
        self._sig_chapter_progress.connect(self._update_chapter_progress)
        self._sig_chapter_status.connect(self._update_chapter_status_slot)
        self._sig_download_finished.connect(self._on_download_finished_slot)

    def _apply_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+A"),  self, self._select_all)
        QShortcut(QKeySequence("Ctrl+D"),  self, self._on_download_clicked)
        QShortcut(QKeySequence("Escape"),  self, self._on_cancel_clicked)
        QShortcut(QKeySequence("Ctrl+,"),  self, self._on_settings_clicked)
        QShortcut(QKeySequence("Return"),  self, self._on_fetch_clicked)

    def eventFilter(self, obj: object, event: QEvent) -> bool:
        if obj is self.url_input and event.type() == QEvent.Type.MouseButtonPress:
            self._url_completer.setCompletionPrefix(self.url_input.text())
            self._url_completer.complete()
        return super().eventFilter(obj, event)

    # ─── theme ────────────────────────────────────────────────────────────────

    def _on_theme_toggle(self) -> None:
        new_theme = "light" if _P.name == "dark" else "dark"
        self._apply_theme(new_theme)

    def _apply_theme(self, theme_name: str) -> None:
        global _P
        effective = (
            _detect_system_theme() if theme_name == "system" else theme_name
        )
        _P = LIGHT_PALETTE if effective == "light" else DARK_PALETTE
        self.config.theme = theme_name
        save_config(self.config)
        self._rebuild_ui()

    def _rebuild_ui(self) -> None:
        # Preserve current state
        url_text    = self.url_input.text() if hasattr(self, "url_input") else ""
        out_dir     = (
            self.output_dir_input.text() if hasattr(self, "output_dir_input")
            else self.config.default_output_dir
        )
        fmt_key     = self._current_format() if hasattr(self, "_format_group") else self.config.output_format
        log_html    = self.log_view.toHtml() if hasattr(self, "log_view") else ""
        saved_manga = getattr(self, "manga", None)

        # Disconnect internal Qt signals to avoid double-connecting after rebuild
        for sig in (
            self._sig_log, self._sig_total_progress, self._sig_chapter_progress,
            self._sig_chapter_status, self._sig_download_finished,
        ):
            try:
                sig.disconnect()
            except RuntimeError:
                pass

        # Rebuild and reconnect (shortcuts are window-level, no need to re-apply)
        self._build_ui()
        self._connect_signals()

        # Restore state
        self.url_input.setText(url_text)
        self.output_dir_input.setText(out_dir)
        if fmt_key in self._format_btns:
            self._format_btns[fmt_key].setChecked(True)
        if log_html:
            self.log_view.setHtml(log_html)

        # Re-populate manga if it was loaded
        if saved_manga:
            self.manga = saved_manga
            self._populate_manga_info(saved_manga)
            self._mark_existing_chapters()

    # ─── button handlers ──────────────────────────────────────────────────────

    def _clear_url(self) -> None:
        self.url_input.clear()
        self._valid_badge.setVisible(False)

    @asyncSlot()
    async def _on_fetch_clicked(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            return
        if not url.startswith(("http://", "https://")):
            self._log("⚠ Invalid URL — must start with http:// or https://")
            return

        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText("⏳  Fetching…")
        self.download_btn.setEnabled(False)
        self._valid_badge.setVisible(False)
        self.chapter_grid.clear()
        self._log(f"Fetching: {url}")

        try:
            site = get_site_for_url(url)
            if not site:
                self._log("⚠ No plugin found for this URL. Supported: truyenqqko.com")
                return

            manga = await site.parse_manga_info(url)
            self.manga = manga
            self._populate_manga_info(manga)
            self._valid_badge.setVisible(True)
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
            self.fetch_btn.setText("🔍  Fetch")

    @asyncSlot()
    async def _on_download_clicked(self) -> None:
        if not self.manga:
            return

        selected = self.chapter_grid.get_selected_chapters()
        if not selected:
            self._log("No chapters selected.")
            return

        output_dir = Path(self.output_dir_input.text().strip() or self.config.default_output_dir)
        export_format = self._current_format()

        self._last_selected = selected
        self.download_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.total_progress.setRange(0, len(selected))
        self.total_progress.setValue(0)
        self.chapter_progress.setValue(0)
        self._active_dot.setText("● ACTIVE")
        self._active_dot.setStyleSheet(
            f"color: {VERM}; font-family:'Courier New',monospace; font-size: 10px;"
        )

        signals = DownloadSignals()
        signals.on_log = self._sig_log.emit
        signals.on_total_progress = self._sig_total_progress.emit
        signals.on_chapter_progress = self._sig_chapter_progress.emit
        signals.on_chapter_status = lambda cid, st: self._sig_chapter_status.emit(cid, st.value)
        signals.on_finished = self._sig_download_finished.emit

        self.downloader = MangaDownloader(self.config, signals)
        await self.downloader.download_manga(self.manga, selected, output_dir, export_format)

        if export_format == "epub":
            try:
                from app.core.exporter import export_manga_epub
                from app.utils.naming import sanitize_filename as sf
                done_chapters = [c for c in selected if c.status == DownloadStatus.DONE]
                if done_chapters:
                    manga_dir = output_dir / sf(self.manga.title)
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
        folder = QFileDialog.getExistingDirectory(
            self, "Select output folder", self.output_dir_input.text()
        )
        if folder:
            self.output_dir_input.setText(folder)

    def _on_settings_clicked(self) -> None:
        from app.ui.settingsDialog import SettingsDialog
        dlg = SettingsDialog(self.config, parent=self)
        dlg.exec()

    def _current_format(self) -> str:
        btn = self._format_group.checkedButton()
        return btn.property("fmt_key") if btn else "pdf"

    # ─── chapter controls ─────────────────────────────────────────────────────

    def _select_all(self)  -> None: self.chapter_grid.select_all()
    def _select_none(self) -> None: self.chapter_grid.select_none()
    def _select_new(self)  -> None: self.chapter_grid.select_new()

    def _apply_range(self) -> None:
        lo, hi = self.range_from.value(), self.range_to.value()
        if lo > hi:
            lo, hi = hi, lo
        self.chapter_grid.select_range(float(lo), float(hi))

    def _on_filter_changed(self, text: str) -> None:
        q = text.lower()
        for card in self.chapter_grid._cards:
            visible = (
                not q
                or q in card.chapter.title.lower()
                or q in str(card.chapter.number)
            )
            card.setVisible(visible)

    def _update_selection_label(self) -> None:
        total = self.chapter_grid.count()
        checked = self.chapter_grid.selected_count()
        self.selection_label.setText(f"{checked} / {total}  SELECTED")
        if self.manga and not self.cancel_btn.isEnabled():
            self.download_btn.setEnabled(checked > 0)
        self._chapters_done_lbl.setText(f"—\n/{total}")

    # ─── populate manga info ──────────────────────────────────────────────────

    def _populate_manga_info(self, manga: Manga) -> None:
        self.title_label.setText(manga.title)
        self.author_val.setText(manga.author or "Unknown")
        self.site_val.setText(manga.site_name)
        self.chapters_val.setText(str(len(manga.chapters)))
        self.status_val.setText("Ongoing")
        self.desc_edit.setPlainText(manga.description or "")

        self.stats_label.setText(
            f"⭐ —   👁 —   ● Ongoing   {len(manga.chapters)} chapters"
        )

        while self._chips_row.count() > 1:
            item = self._chips_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        genres = getattr(manga, "genres", []) or []
        if genres:
            for g in genres[:8]:
                chip = QLabel(g)
                chip.setStyleSheet(
                    f"color: {_P.INK_DIM}; background: {_P.PAPER_3};"
                    f" border: 1px solid {_P.LINE_SOFT}; border-radius: 99px;"
                    f" padding: 2px 8px; font-size: 10px; letter-spacing: .4px;"
                )
                self._chips_row.insertWidget(self._chips_row.count() - 1, chip)

        self.chapter_grid.clear()
        max_n = max((c.number for c in manga.chapters), default=1) or 1
        self.range_from.setRange(1, int(max_n))
        self.range_to.setRange(1, int(max_n))
        self.range_to.setValue(int(max_n))

        for chapter in manga.chapters:
            self.chapter_grid.add_chapter(chapter)

        self._mark_existing_chapters()
        self._update_selection_label()

        if manga.cover_url:
            self._load_cover(manga.cover_url, manga.url)

    def _mark_existing_chapters(self) -> None:
        if not self.manga:
            return
        output_dir = Path(self.output_dir_input.text())
        fmt = self._current_format()
        manga_dir = output_dir / sanitize_filename(self.manga.title) / fmt
        for card in self.chapter_grid._cards:
            chapter_dir = manga_dir / f"Chapter_{chapter_stem(card.chapter.number)}"
            exists = chapter_dir.is_dir() and any(chapter_dir.iterdir())
            card.mark_existing(exists)

    def _load_cover(self, cover_url: str, referer: str) -> None:
        req = QNetworkRequest(QUrl(cover_url))
        req.setRawHeader(b"Referer", referer.encode())
        req.setRawHeader(
            b"User-Agent",
            b"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        reply = self._nam.get(req)
        reply.finished.connect(lambda: self._on_cover_reply(reply))

    def _on_cover_reply(self, reply: QNetworkReply) -> None:
        if reply.error() == QNetworkReply.NoError:
            pixmap = QPixmap()
            pixmap.loadFromData(reply.readAll())
            if not pixmap.isNull():
                self.cover_label.setText("")
                self.cover_label.setPixmap(
                    pixmap.scaled(120, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
        reply.deleteLater()

    # ─── progress / log slots ─────────────────────────────────────────────────

    @Slot(str)
    def _append_log(self, msg: str) -> None:
        kind  = _log_kind(msg)
        color = _kind_color(kind)
        kind_label = kind.upper().ljust(4)
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        escaped = msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        line = (
            f'<span style="color:{_P.INK_FAINT};">{ts}</span>  '
            f'<span style="color:{color};">{kind_label}</span>  '
            f'<span style="color:{_P.INK_DIM};">{escaped}</span>'
        )
        self.log_view.append(line)

    @Slot(int, int)
    def _update_total_progress(self, done: int, total: int) -> None:
        self.total_progress.setRange(0, total)
        self.total_progress.setValue(done)
        pct = (done / total * 100) if total else 0
        self.progress_ring.setValue(pct)
        self._chapters_done_lbl.setText(f"{done}\n/{total}")

    @Slot(int, int)
    def _update_chapter_progress(self, done: int, total: int) -> None:
        self.chapter_progress.setRange(0, total)
        self.chapter_progress.setValue(done)

    def _update_chapter_status_slot(self, chapter_id: int, status_value: str) -> None:
        status = DownloadStatus(status_value)
        self.chapter_grid.update_status(chapter_id, status)
        if status == DownloadStatus.DOWNLOADING:
            card = self.chapter_grid._card_map.get(chapter_id)
            if card:
                n = card.chapter.number
                n_str = f"#{int(n):03d}" if n == int(n) else f"#{n}"
                self._current_chapter_lbl.setText(
                    f'<span style="color:{VERM};">{n_str}</span>'
                    f' — {card.chapter.title}'
                )

    @Slot()
    def _on_download_finished_slot(self) -> None:
        self.cancel_btn.setEnabled(False)
        self._active_dot.setText("● IDLE")
        self._active_dot.setStyleSheet(
            f"color: {_P.INK_FAINT}; font-family:'Courier New',monospace; font-size: 10px;"
        )
        self._current_chapter_lbl.setText("—")
        self._mark_existing_chapters()
        self._update_selection_label()

        failed = [c for c in self._last_selected if c.status == DownloadStatus.FAILED]
        done   = [c for c in self._last_selected if c.status == DownloadStatus.DONE]
        total  = len(self._last_selected)

        self._log("─" * 38)
        if not failed:
            self._log(f"✓ Download finished — {len(done)}/{total} chapters completed.")
        else:
            self._log(f"✗ Download finished — {len(failed)}/{total} chapters FAILED:")
            for ch in failed:
                self._log(f"  ✗ {ch.title}")

        if failed:
            msg = QMessageBox(self)
            msg.setWindowTitle("Download Errors")
            msg.setIcon(QMessageBox.Warning)
            msg.setText(f"{len(failed)} chapter(s) failed to download.")
            msg.setDetailedText("\n".join(f"• {ch.title}" for ch in failed))
            msg.exec()

    def _log(self, msg: str) -> None:
        self._append_log(msg)
