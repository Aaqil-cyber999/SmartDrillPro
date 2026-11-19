"""Basic file upload interface.

Phase 2 copies files into the project and detects duplicates. Real content
validation, layer classification and geometry parsing arrive in Phase 3.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.application import Application

ALLOWED_SUFFIXES = {
    ".gbr", ".ger", ".gtl", ".gbl", ".gts", ".gbs", ".gto", ".gbo",
    ".gm1", ".gko", ".drl", ".xln", ".txt", ".zip",
}


class FileManagerPage(QWidget):
    def __init__(self, core: Application) -> None:
        super().__init__()
        self.core = core

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        title = QLabel("File manager")
        title.setObjectName("pageTitle")
        self.project_label = QLabel("No project is open.")
        self.project_label.setObjectName("subtitle")
        root.addWidget(title)
        root.addWidget(self.project_label)

        note = QLabel(
            "Phase 2: files are copied into the project and checked for duplicates by "
            "name and SHA-256 hash. Content validation and layer detection are added in Phase 3."
        )
        note.setWordWrap(True)
        note.setObjectName("noticeText")
        root.addWidget(note)

        buttons = QHBoxLayout()
        add = QPushButton("Add manufacturing files")
        add.setObjectName("primaryButton")
        add.clicked.connect(self.add_files)
        remove = QPushButton("Remove selected")
        remove.clicked.connect(self.remove_selected)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch(1)
        root.addLayout(buttons)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["File", "Kind", "Size (bytes)", "SHA-256"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        root.addWidget(self.table)

        self.core.events.subscribe("project_changed", lambda *_: self.refresh())
        self.core.events.subscribe("files_added", lambda *_: self.refresh())
        self.refresh()

    def add_files(self) -> None:
        if self.core.projects.active is None:
            QMessageBox.information(self, "SmartDrill Pro", "Create or open a project first.")
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Gerber or Excellon files",
            "",
            "Manufacturing files (*.gbr *.ger *.gtl *.gbl *.gts *.gbs *.gto *.gbo *.gm1 *.gko *.drl *.xln *.txt *.zip);;All files (*.*)",
        )
        if not paths:
            return
        selected = [Path(path) for path in paths]
        unsupported = [p.name for p in selected if p.suffix.lower() not in ALLOWED_SUFFIXES]
        accepted = [p for p in selected if p.suffix.lower() in ALLOWED_SUFFIXES]

        added, skipped = self.core.projects.add_source_files(accepted)
        messages: list[str] = []
        if added:
            messages.append(f"Added {len(added)} file(s).")
        if skipped:
            messages.append("Skipped:\n- " + "\n- ".join(skipped))
        if unsupported:
            messages.append("Unsupported extension (content check comes in Phase 3):\n- " + "\n- ".join(unsupported))
        QMessageBox.information(self, "Import result", "\n\n".join(messages) or "Nothing to import.")

    def remove_selected(self) -> None:
        project = self.core.projects.active
        if project is None:
            return
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(self, "SmartDrill Pro", "Select a file first.")
            return
        rows = {item.row() for item in selected}
        project_dir = self.core.projects.active_dir_or_raise
        for row in rows:
            record = project.source_files[row]
            copied_file = project_dir / record.relative_path
            if copied_file.is_file():
                copied_file.unlink()
        removed_names = [project.source_files[row].name for row in sorted(rows)]
        project.source_files = [item for index, item in enumerate(project.source_files) if index not in rows]
        self.core.projects.save()
        self.core.events.emit("files_removed", project, removed_names)
        self.refresh()

    def refresh(self) -> None:
        project = self.core.projects.active
        if project is None:
            self.project_label.setText("No project is open. Create one on the 'New PCB Project' page.")
        else:
            self.project_label.setText(f"Active project: {project.name}  |  {len(project.source_files)} file(s)")

        self.table.setRowCount(0)
        for record in project.source_files if project else []:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(record.name))
            self.table.setItem(row, 1, QTableWidgetItem(Path(record.name).suffix.lower() or "none"))
            self.table.setItem(row, 2, QTableWidgetItem(str(record.size_bytes)))
            self.table.setItem(row, 3, QTableWidgetItem(record.sha256[:16] + "..."))
