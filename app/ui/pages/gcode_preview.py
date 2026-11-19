"""G-code preview and validation page. Generated code is never auto-executed."""

from __future__ import annotations

from pathlib import Path
import shutil

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.application import Application
from app.gcode.gcode_normalizer import normalize_gcode, validated_copy_path
from app.gcode.gcode_parser import parse_gcode
from app.gcode.gcode_validator import validate_gcode
from app.ui.widgets.gcode_preview import GcodePreviewView


class GcodePreviewPage(QWidget):
    def __init__(self, core: Application) -> None:
        super().__init__()
        self.core = core
        self.current_path: Path | None = None
        self.current_report = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)
        title = QLabel("G-code preview")
        title.setObjectName("pageTitle")
        self.status = QLabel("No project is open.")
        self.status.setObjectName("subtitle")
        root.addWidget(title)
        root.addWidget(self.status)

        note = QLabel(
            "Generated G-code is inspected here only. Nothing is sent to a machine from this page; "
            "Machine Control requires an explicit validated job selection."
        )
        note.setObjectName("noticeText")
        note.setWordWrap(True)
        root.addWidget(note)

        controls = QHBoxLayout()
        self.file_combo = QComboBox()
        self.file_combo.setMinimumWidth(320)
        load = QPushButton("Load and validate")
        load.setObjectName("primaryButton")
        load.clicked.connect(self.load_selected)
        validated = QPushButton("Create validated copy")
        validated.clicked.connect(self.create_validated_copy)
        export = QPushButton("Export G-code")
        export.clicked.connect(self.export_gcode)
        controls.addWidget(self.file_combo)
        controls.addWidget(load)
        controls.addWidget(validated)
        controls.addWidget(export)
        controls.addStretch(1)
        root.addLayout(controls)

        self.preview = GcodePreviewView()
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setPlaceholderText("Validation results appear here.")
        content = QHBoxLayout()
        content.addWidget(self.preview, 2)
        content.addWidget(self.report, 1)
        root.addLayout(content, 1)

        for event in ("project_changed", "cam_jobs_changed", "files_removed"):
            self.core.events.subscribe(event, lambda *_: self.refresh())
        self.refresh()

    def gcode_directory(self) -> Path | None:
        if self.core.projects.active_dir is None:
            return None
        return self.core.projects.active_dir / "generated" / "gcode"

    def refresh(self) -> None:
        self.file_combo.clear()
        directory = self.gcode_directory()
        if self.core.projects.active is None:
            self.status.setText("No project is open. Generate G-code in CAM Processing first.")
            return
        files = sorted(directory.glob("*.nc")) if directory else []
        self.file_combo.addItems([path.name for path in files])
        self.status.setText(
            f"Project '{self.core.projects.active.name}' | {len(files)} G-code file(s)"
        )
        if not files:
            self.preview.set_gcode(None)
            self.report.setPlainText("No G-code has been generated yet.")

    def load_selected(self) -> None:
        directory = self.gcode_directory()
        name = self.file_combo.currentText()
        if directory is None or not name:
            QMessageBox.information(self, "SmartDrill Pro", "Select a G-code file first.")
            return
        path = directory / name
        self.current_path = path
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            QMessageBox.warning(self, "SmartDrill Pro", f"Cannot read {name}: {exc}")
            return

        parsed = parse_gcode(text, source=name)
        report = validate_gcode(
            parsed, self.core.settings, self.core.active_profile
        )
        self.current_report = report
        self.preview.set_gcode(parsed)

        lines = [
            f"File: {name}",
            f"Lines: {parsed.line_count} | Moves: {len(parsed.moves)}",
            f"Units: {parsed.units} | Move counts: {report.move_counts}",
            f"Estimated cutting time: {report.estimated_time_s / 60:.1f} min",
            f"Bounds (mm): {report.bounds}",
            "",
            "SAFE" if report.safe else "NOT SAFE - fix errors before use",
        ]
        for issue in report.issues:
            location = f" line {issue.line}" if issue.line else ""
            lines.append(f"[{issue.severity.upper()}]{location} {issue.message}")
        self.report.setPlainText("\n".join(lines))

    def create_validated_copy(self) -> None:
        if self.current_path is None or self.current_report is None:
            QMessageBox.information(self, "SmartDrill Pro", "Load and validate a G-code file first.")
            return
        if not self.current_report.safe:
            QMessageBox.warning(
                self, "SmartDrill Pro",
                "Fix validation errors before creating a validated copy.",
            )
            return
        try:
            normalized = normalize_gcode(
                self.current_path.read_text(encoding="utf-8", errors="replace")
            )
        except ValueError as exc:
            QMessageBox.warning(self, "SmartDrill Pro", str(exc))
            return

        revalidated = validate_gcode(
            parse_gcode(normalized, source=self.current_path.name),
            self.core.settings,
            self.core.active_profile,
        )
        if not revalidated.safe:
            QMessageBox.warning(
                self, "SmartDrill Pro",
                "Normalized copy failed re-validation:\n"
                + "\n".join(issue.message for issue in revalidated.errors),
            )
            return

        target = self.current_path.with_name(validated_copy_path(self.current_path.name))
        target.write_text(normalized, encoding="utf-8")
        self.current_report = revalidated
        QMessageBox.information(
            self, "SmartDrill Pro", f"Validated copy written to {target.name}. Original file unchanged."
        )
        self.load_path(target)
        self.refresh()
        index = self.file_combo.findText(target.name)
        if index >= 0:
            self.file_combo.setCurrentIndex(index)

    def load_path(self, path: Path) -> None:
        """Load a specific file into the validation view."""
        self.current_path = path
        text = path.read_text(encoding="utf-8", errors="replace")
        parsed = parse_gcode(text, source=path.name)
        self.current_report = validate_gcode(parsed, self.core.settings, self.core.active_profile)
        self.preview.set_gcode(parsed)
        self.report.setPlainText(
            f"File: {path.name}\nSAFE" if self.current_report.safe else
            f"File: {path.name}\nNOT SAFE: " + ", ".join(
                issue.message for issue in self.current_report.errors
            )
        )

    def export_gcode(self) -> None:
        if self.current_path is None:
            QMessageBox.information(self, "SmartDrill Pro", "Select a G-code file first.")
            return
        target, _ = QFileDialog.getSaveFileName(
            self, "Export G-code", self.current_path.name, "G-code (*.nc *.gcode *.txt)"
        )
        if not target:
            return
        shutil.copy2(self.current_path, target)
        QMessageBox.information(self, "SmartDrill Pro", f"Exported to {target}")
