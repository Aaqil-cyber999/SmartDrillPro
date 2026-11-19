"""Manufacturing file import page.

Supports individual files, whole folders, ZIP bundles and drag-and-drop. Every
file is content-validated, classified and parsed before it is accepted.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QComboBox,
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
from app.file_processing.layer_classifier import LAYER_ROLES

FILE_FILTER = (
    "Manufacturing files (*.gbr *.ger *.gtl *.gbl *.gts *.gbs *.gto *.gbo "
    "*.gm1 *.gko *.drl *.xln *.txt *.zip);;All files (*.*)"
)


class FileManagerPage(QWidget):
    def __init__(self, core: Application) -> None:
        super().__init__()
        self.core = core
        self.setAcceptDrops(True)

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
            "Import Gerber and Excellon files, a complete folder, or a ZIP bundle. "
            "Files are validated by content and copied into the project unchanged. "
            "You can override any detected layer role below."
        )
        note.setWordWrap(True)
        note.setObjectName("noticeText")
        root.addWidget(note)

        buttons = QHBoxLayout()
        add = QPushButton("Add manufacturing files")
        add.setObjectName("primaryButton")
        add.clicked.connect(self.add_files)
        add_folder = QPushButton("Add folder")
        add_folder.clicked.connect(self.add_folder)
        add_zip = QPushButton("Add ZIP bundle")
        add_zip.clicked.connect(self.add_zip)
        remove = QPushButton("Remove selected")
        remove.clicked.connect(self.remove_selected)
        buttons.addWidget(add)
        buttons.addWidget(add_folder)
        buttons.addWidget(add_zip)
        buttons.addWidget(remove)
        buttons.addStretch(1)
        root.addLayout(buttons)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "File", "Content", "Detected layer", "Confidence", "Features", "SHA-256"
        ])
        for column in (0, 2, 5):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        root.addWidget(self.table)

        self.core.events.subscribe("project_changed", lambda *_: self.refresh())
        self.core.events.subscribe("files_added", lambda *_: self.refresh())
        self.core.events.subscribe("files_removed", lambda *_: self.refresh())
        self.core.events.subscribe("layers_changed", lambda *_: self.refresh())
        self.refresh()

    # ------------------------------------------------------------------
    # Import entry points
    # ------------------------------------------------------------------
    def add_files(self) -> None:
        if not self._require_project():
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Gerber or Excellon files", "", FILE_FILTER)
        if paths:
            self._import([Path(path) for path in paths])

    def add_folder(self) -> None:
        if not self._require_project():
            return
        folder = QFileDialog.getExistingDirectory(self, "Select a folder of manufacturing files")
        if folder:
            self._import([Path(folder)])

    def add_zip(self) -> None:
        if not self._require_project():
            return
        archive, _ = QFileDialog.getOpenFileName(self, "Select a ZIP bundle", "", "ZIP files (*.zip)")
        if archive:
            self._import([Path(archive)])

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        if not self._require_project():
            return
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.toLocalFile()]
        if paths:
            event.acceptProposedAction()
            self._import(paths)

    def _require_project(self) -> bool:
        if self.core.projects.active is None:
            QMessageBox.information(self, "SmartDrill Pro", "Create or open a project first.")
            return False
        return True

    def _import(self, paths: list[Path]) -> None:
        outcome = self.core.importer.import_paths(paths)
        messages: list[str] = []
        if outcome.added:
            messages.append(f"Imported {len(outcome.added)} file(s):\n- " + "\n- ".join(
                f"{item.name} → {item.layer_role} ({item.layer_confidence:.0%})" for item in outcome.added
            ))
        if outcome.skipped:
            messages.append("Skipped:\n- " + "\n- ".join(outcome.skipped))
        if outcome.errors:
            messages.append("Errors:\n- " + "\n- ".join(outcome.errors))
        QMessageBox.information(self, "Import result", "\n\n".join(messages) or "Nothing to import.")
        self.refresh()

    # ------------------------------------------------------------------
    # Table management
    # ------------------------------------------------------------------
    def remove_selected(self) -> None:
        project = self.core.projects.active
        if project is None:
            return
        rows = {item.row() for item in self.table.selectedItems()}
        if not rows:
            QMessageBox.information(self, "SmartDrill Pro", "Select a file first.")
            return
        project_dir = self.core.projects.active_dir_or_raise
        for row in rows:
            record = project.source_files[row]
            copied_file = project_dir / record.relative_path
            if copied_file.is_file():
                copied_file.unlink()
        removed_names = [project.source_files[row].name for row in sorted(rows)]
        project.source_files = [item for index, item in enumerate(project.source_files) if index not in rows]
        project.layers = [layer for layer in project.layers if layer.get("file") not in removed_names]
        self.core.projects.save()
        self.core.events.emit("files_removed", project, removed_names)
        self.refresh()

    def _role_changed(self, row: int) -> None:
        combo = self.table.cellWidget(row, 2)
        if combo is None:
            return
        name_item = self.table.item(row, 0)
        if name_item is None:
            return
        self.core.importer.set_layer_role(name_item.text(), combo.currentText())
        self.refresh()

    def refresh(self) -> None:
        project = self.core.projects.active
        if project is None:
            self.project_label.setText("No project is open. Create one on the 'New PCB Project' page.")
        else:
            self.project_label.setText(
                f"Active project: {project.name}  |  {len(project.source_files)} file(s)  |  "
                f"{len(project.layers)} layer(s) detected"
            )

        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for record in project.source_files if project else []:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(record.name))
            self.table.setItem(row, 1, QTableWidgetItem(record.content_type))
            combo = QComboBox()
            combo.blockSignals(True)
            combo.addItems(list(LAYER_ROLES))
            combo.setCurrentText(record.layer_role if record.layer_role in LAYER_ROLES else "other")
            combo.blockSignals(False)
            combo.currentIndexChanged.connect(lambda _index, current=row: self._role_changed(current))
            self.table.setCellWidget(row, 2, combo)
            confidence = QTableWidgetItem(f"{record.layer_confidence:.0%}")
            confidence.setToolTip(record.layer_reason)
            self.table.setItem(row, 3, confidence)
            self.table.setItem(row, 4, QTableWidgetItem(str(record.feature_count)))
            self.table.setItem(row, 5, QTableWidgetItem(record.sha256[:16] + "..."))
        self.table.blockSignals(False)
