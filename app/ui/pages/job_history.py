"""Job history from the active project's persisted records."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.application import Application
from app.ui.event_bridge import QtEventBridge


class JobHistoryPage(QWidget):
    def __init__(self, core: Application) -> None:
        super().__init__()
        self.core = core
        self.bridge = QtEventBridge(core.events, ("job_finished",), self)
        self.bridge.event_received.connect(lambda *_: self.refresh())
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)
        title = QLabel("Job history")
        title.setObjectName("pageTitle")
        self.summary = QLabel("No project is open.")
        self.summary.setObjectName("subtitle")
        root.addWidget(title)
        root.addWidget(self.summary)

        controls = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        controls.addWidget(refresh)
        controls.addStretch(1)
        root.addLayout(controls)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Started", "G-code file", "Mode", "Lines", "Status", "Duration (s)", "Error"
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table)

        for event in ("project_changed",):
            self.core.events.subscribe(event, lambda *_: self.refresh())
        self.refresh()

    def refresh(self) -> None:
        project = self.core.projects.active
        jobs = project.machine_jobs if project else []
        self.summary.setText(
            f"No project is open." if project is None else
            f"Project '{project.name}' | {len(jobs)} machine job(s) | "
            f"records are saved in project.json"
        )
        self.table.setRowCount(0)
        for job in jobs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                job.get("started_at", ""),
                job.get("file", ""),
                "Simulation" if job.get("simulation") else "Real machine",
                str(job.get("lines", "")),
                job.get("status", ""),
                str(job.get("duration_s", "")),
                job.get("error", ""),
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
