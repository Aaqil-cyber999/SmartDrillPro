"""Application preferences and conservative safety limits."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.application import Application


class SettingsPage(QWidget):
    def __init__(self, core: Application) -> None:
        super().__init__()
        self.core = core
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        title = QLabel("Settings")
        title.setObjectName("pageTitle")
        note = QLabel(
            "Safety limits are conservative defaults, not cutting recommendations. "
            "Serial settings apply after reconnecting."
        )
        note.setObjectName("noticeText")
        note.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(note)

        settings = core.settings
        form = QFormLayout()
        self.simulation = QCheckBox("Simulation mode (no physical machine commands)")
        self.simulation.setChecked(settings.simulation_mode)
        form.addRow("Mode", self.simulation)

        self.baud = QSpinBox()
        self.baud.setRange(1200, 2000000)
        self.baud.setValue(settings.baud_rate)
        form.addRow("Serial baud rate", self.baud)

        self.rx = QSpinBox()
        self.rx.setRange(64, 4096)
        self.rx.setValue(settings.rx_buffer_bytes)
        form.addRow("Controller RX buffer (bytes)", self.rx)

        self.poll = QSpinBox()
        self.poll.setRange(100, 10000)
        self.poll.setValue(settings.status_poll_ms)
        form.addRow("Status poll interval (ms)", self.poll)

        self.cut_depth = self._double(0.1, 100.0, settings.max_cut_depth_mm, 2)
        self.feed = QSpinBox()
        self.feed.setRange(1, 10000)
        self.feed.setValue(settings.max_feed_rate_mm_min)
        self.plunge = QSpinBox()
        self.plunge.setRange(1, 10000)
        self.plunge.setValue(settings.max_plunge_rate_mm_min)
        form.addRow("Max cut depth (mm)", self.cut_depth)
        form.addRow("Max XY feed (mm/min)", self.feed)
        form.addRow("Max plunge feed (mm/min)", self.plunge)

        self.flatcam_python = QLineEdit(settings.flatcam_python)
        self.flatcam_python.setPlaceholderText("Auto-detect .venv-flatcam")
        self.flatcam_root = QLineEdit(settings.flatcam_root)
        self.flatcam_root.setPlaceholderText("Auto-detect tools/flatcam")
        form.addRow("FlatCAM Python", self.flatcam_python)
        form.addRow("FlatCAM source", self.flatcam_root)
        root.addLayout(form)

        save = QPushButton("Save settings")
        save.setObjectName("primaryButton")
        save.clicked.connect(self.save)
        root.addWidget(save)

    @staticmethod
    def _double(minimum: float, maximum: float, value: float, decimals: int) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setValue(value)
        return spin

    def save(self) -> None:
        settings = self.core.settings
        settings.simulation_mode = self.simulation.isChecked()
        settings.baud_rate = self.baud.value()
        settings.rx_buffer_bytes = self.rx.value()
        settings.status_poll_ms = self.poll.value()
        settings.max_cut_depth_mm = self.cut_depth.value()
        settings.max_feed_rate_mm_min = self.feed.value()
        settings.max_plunge_rate_mm_min = self.plunge.value()
        settings.flatcam_python = self.flatcam_python.text().strip()
        settings.flatcam_root = self.flatcam_root.text().strip()
        self.core.save_settings()
        QMessageBox.information(self, "Settings", "Settings saved to settings.json.")
