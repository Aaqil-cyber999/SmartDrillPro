"""Dashboard: workflow guidance and quick actions."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from config.application_config import APP_VERSION, WORKFLOW_STEPS


class DashboardPage(QWidget):
    navigate_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("dashboard")

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

        title = QLabel("PCB CNC manufacturing, in one place")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Import Gerber and Excellon files, prepare machining operations, validate "
            "G-code, then control the machine from a single workspace."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("subtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        banner = QFrame()
        banner.setObjectName("noticeCard")
        banner_layout = QHBoxLayout(banner)
        banner_layout.addWidget(
            QLabel(
                "SAFETY: software stop is not a hardware emergency stop. "
                "Always verify the machine and toolpath before cutting."
            )
        )
        root.addWidget(banner)

        actions = QHBoxLayout()
        create_button = QPushButton("Create a new project")
        create_button.setObjectName("primaryButton")
        create_button.clicked.connect(lambda: self.navigate_requested.emit("New PCB Project"))
        files_button = QPushButton("Open file manager")
        files_button.clicked.connect(lambda: self.navigate_requested.emit("File Manager"))
        actions.addWidget(create_button)
        actions.addWidget(files_button)
        actions.addStretch(1)
        root.addLayout(actions)

        steps_label = QLabel("Recommended workflow")
        steps_label.setObjectName("sectionTitle")
        root.addWidget(steps_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        steps_widget = QWidget()
        steps_layout = QVBoxLayout(steps_widget)
        steps_layout.setSpacing(6)
        for number, text in WORKFLOW_STEPS:
            row = QHBoxLayout()
            badge = QLabel(number)
            badge.setObjectName("stepBadge")
            badge.setFixedWidth(28)
            label = QLabel(text)
            row.addWidget(badge)
            row.addWidget(label)
            row.addStretch(1)
            frame = QFrame()
            frame.setObjectName("stepCard")
            frame.setLayout(row)
            steps_layout.addWidget(frame)
        steps_layout.addStretch(1)
        scroll.setWidget(steps_widget)
        root.addWidget(scroll)

        version = QLabel(f"SmartDrill Pro {APP_VERSION} - Phase 2 foundation")
        version.setObjectName("footerNote")
        root.addWidget(version)
