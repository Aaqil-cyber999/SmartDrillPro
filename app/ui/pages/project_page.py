"""Project creation and opening."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.application import Application


class ProjectPage(QWidget):
    def __init__(self, core: Application) -> None:
        super().__init__()
        self.core = core

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        title = QLabel("New PCB project")
        title.setObjectName("pageTitle")
        description = QLabel(
            "A project keeps your original files, processing settings, generated G-code "
            "and job history together. Original files are never overwritten."
        )
        description.setWordWrap(True)
        description.setObjectName("subtitle")
        root.addWidget(title)
        root.addWidget(description)

        form = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Example: Sensor Board Rev A")
        self.name_edit.returnPressed.connect(self.create_project)
        create = QPushButton("Create project")
        create.setObjectName("primaryButton")
        create.clicked.connect(self.create_project)
        form.addWidget(self.name_edit, 1)
        form.addWidget(create)
        root.addLayout(form)

        section = QLabel("Existing projects")
        section.setObjectName("sectionTitle")
        root.addWidget(section)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Project", "Created (UTC)", "Location"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        root.addWidget(self.table)

        buttons = QHBoxLayout()
        open_button = QPushButton("Open selected project")
        open_button.clicked.connect(self.open_selected)
        refresh = QPushButton("Refresh list")
        refresh.clicked.connect(self.refresh)
        buttons.addWidget(open_button)
        buttons.addWidget(refresh)
        buttons.addStretch(1)
        root.addLayout(buttons)

        self.core.events.subscribe("project_created", lambda *_: self.refresh())
        self.refresh()

    def create_project(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "SmartDrill Pro", "Enter a project name first.")
            return
        try:
            project, _ = self.core.projects.create_project(name)
        except ValueError as exc:
            QMessageBox.warning(self, "Could not create project", str(exc))
            return
        self.name_edit.clear()
        QMessageBox.information(
            self,
            "Project created",
            f"'{project.name}' is ready. Add Gerber and Excellon files in the File Manager.",
        )

    def refresh(self) -> None:
        self.table.setRowCount(0)
        for project, project_dir in self.core.projects.list_projects():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(project.name))
            self.table.setItem(row, 1, QTableWidgetItem(project.created_at))
            self.table.setItem(row, 2, QTableWidgetItem(str(project_dir)))

    def open_selected(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(self, "SmartDrill Pro", "Select a project first.")
            return
        location = Path(self.table.item(selected[0].row(), 2).text())
        try:
            self.core.projects.open_project(location)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Could not open project", str(exc))
