from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QGroupBox, QLabel, QLineEdit, QSpinBox, QVBoxLayout,
)
from PySide6.QtCore import Qt

from app.core.config import AppConfig, save_config


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Settings")
        self.setMinimumWidth(420)
        self._build_ui()
        self._load_values()

    # ─── UI ─────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Download group
        dl_group = QGroupBox("Download")
        dl_form = QFormLayout(dl_group)

        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 20)
        dl_form.addRow("Concurrent images:", self.concurrent_spin)

        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.0, 10.0)
        self.delay_spin.setSingleStep(0.5)
        self.delay_spin.setSuffix(" s")
        dl_form.addRow("Delay between chapters:", self.delay_spin)

        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 10)
        dl_form.addRow("Retry count:", self.retry_spin)

        # Network group
        net_group = QGroupBox("Network")
        net_form = QFormLayout(net_group)

        self.ua_input = QLineEdit()
        self.ua_input.setPlaceholderText("Leave empty to rotate automatically")
        net_form.addRow("Custom User-Agent:", self.ua_input)

        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("http://user:pass@host:port")
        net_form.addRow("Proxy:", self.proxy_input)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(dl_group)
        layout.addWidget(net_group)
        layout.addWidget(buttons)

    def _load_values(self) -> None:
        self.concurrent_spin.setValue(self.config.concurrent_downloads)
        self.delay_spin.setValue(self.config.delay_seconds)
        self.retry_spin.setValue(self.config.retry_count)
        self.ua_input.setText(self.config.user_agent or "")
        self.proxy_input.setText(self.config.proxy or "")

    def _on_accept(self) -> None:
        self.config.concurrent_downloads = self.concurrent_spin.value()
        self.config.delay_seconds = self.delay_spin.value()
        self.config.retry_count = self.retry_spin.value()
        ua = self.ua_input.text().strip()
        self.config.user_agent = ua or None
        proxy = self.proxy_input.text().strip()
        self.config.proxy = proxy or None
        save_config(self.config)
        self.accept()
