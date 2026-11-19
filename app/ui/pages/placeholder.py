"""Honest placeholders for features scheduled in later phases.

These screens explain what is planned instead of displaying fake data.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaceholderPage(QWidget):
    def __init__(self, title: str, phase: str, description: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(10)

        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        status = QLabel(f"Planned for {phase} - not implemented yet")
        status.setObjectName("statusChip")
        body = QLabel(description)
        body.setWordWrap(True)
        body.setObjectName("subtitle")
        layout.addWidget(heading)
        layout.addWidget(status)
        layout.addWidget(body)
        layout.addStretch(1)
