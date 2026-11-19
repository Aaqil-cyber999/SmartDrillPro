"""CAM processing page: configure parameters and run the real FlatCAM worker."""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.cam.cam_settings import CamSettings
from app.cam.cam_service import CamRunResult
from app.core.application import Application
from app.ui.event_bridge import QtEventBridge


class CamWorker(QObject):
    finished = Signal(object)

    def __init__(self, core: Application, settings: CamSettings) -> None:
        super().__init__()
        self.core = core
        self.settings = settings

    @Slot()
    def run_job(self) -> None:
        result = self.core.cam.run(self.settings)
        self.finished.emit(result)


class CamProcessingPage(QWidget):
    def __init__(self, core: Application) -> None:
        super().__init__()
        self.core = core
        self._thread: QThread | None = None
        self.bridge = QtEventBridge(core.events, ("cam_jobs_changed",), self)
        self.bridge.event_received.connect(lambda *_: self.refresh())

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)
        title = QLabel("CAM processing")
        title.setObjectName("pageTitle")
        self.status = QLabel("No project is open.")
        self.status.setObjectName("subtitle")
        root.addWidget(title)
        self.status.setTextInteractionFlags(self.status.textInteractionFlags())
        root.addWidget(self.status)

        available, reason = core.cam.adapter.available
        self.worker_status = QLabel(("Worker ready. " if available else "Worker unavailable. ") + reason)
        self.worker_status.setObjectName("noticeText" if not available else "subtitle")
        root.addWidget(self.worker_status)

        form = QFormLayout()
        self.isolation = QCheckBox("Isolation routing (top or bottom copper)")
        self.drilling = QCheckBox("Drilling (Excellon)")
        self.outline = QCheckBox("Board outline (Edge_Cuts)")
        form.addRow("Operations", self.isolation)
        form.addRow("", self.drilling)
        form.addRow("", self.outline)

        self.iso_tool = self._double(0.05, 10.0, 0.4, 3)
        self.iso_passes = QSpinBox()
        self.iso_passes.setRange(1, 10)
        self.iso_passes.setValue(1)
        self.iso_overlap = self._double(0.0, 99.0, 0.0, 1)
        self.cut_depth = self._double(-20.0, -0.01, -0.1, 3)
        self.travel_height = self._double(0.1, 100.0, 2.0, 2)
        self.depth_per_pass = self._double(0.01, 10.0, 0.1, 2)
        self.feed_xy = self._double(1.0, 5000.0, 120.0, 0)
        self.feed_z = self._double(1.0, 5000.0, 100.0, 0)
        self.feed_rapid = self._double(1.0, 5000.0, 300.0, 0)
        self.spindle = QSpinBox()
        self.spindle.setRange(0, 60000)
        self.spindle.setValue(1000)
        self.outline_tool = self._double(0.05, 20.0, 0.8, 3)
        self.outline_depth = self._double(-20.0, -0.01, -1.6, 3)
        self.drill_depth = self._double(-20.0, -0.01, -1.6, 3)

        form.addRow("Isolation tool (mm)", self.iso_tool)
        form.addRow("Isolation passes", self.iso_passes)
        form.addRow("Pass overlap (%)", self.iso_overlap)
        form.addRow("Isolation cut Z (mm)", self.cut_depth)
        form.addRow("Travel height (mm)", self.travel_height)
        form.addRow("Depth per pass (mm)", self.depth_per_pass)
        form.addRow("XY feed (mm/min)", self.feed_xy)
        form.addRow("Plunge feed (mm/min)", self.feed_z)
        form.addRow("Rapid feed (mm/min)", self.feed_rapid)
        form.addRow("Spindle (rpm)", self.spindle)
        form.addRow("Outline tool (mm)", self.outline_tool)
        form.addRow("Outline depth (mm)", self.outline_depth)
        form.addRow("Drill depth (mm)", self.drill_depth)
        root.addLayout(form)

        buttons = QHBoxLayout()
        self.generate = QPushButton("Generate toolpaths with FlatCAM")
        self.generate.setObjectName("primaryButton")
        self.generate.clicked.connect(self.start_job)
        save = QPushButton("Save parameters")
        save.clicked.connect(self.save_settings)
        buttons.addWidget(self.generate)
        buttons.addWidget(save)
        buttons.addStretch(1)
        root.addLayout(buttons)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("FlatCAM progress and results appear here.")
        root.addWidget(self.output, 1)

        for event in ("project_changed", "files_added", "files_removed", "layers_changed"):
            self.core.events.subscribe(event, lambda *_: self.refresh())
        self.refresh()

    @staticmethod
    def _double(minimum: float, maximum: float, value: float, decimals: int) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setValue(value)
        return spin

    def current_settings(self) -> CamSettings:
        return CamSettings(
            isolation_tool_mm=self.iso_tool.value(),
            isolation_passes=self.iso_passes.value(),
            isolation_overlap=self.iso_overlap.value(),
            cut_depth_mm=self.cut_depth.value(),
            travel_height_mm=self.travel_height.value(),
            depth_per_pass_mm=self.depth_per_pass.value(),
            feed_xy=self.feed_xy.value(),
            feed_z=self.feed_z.value(),
            feed_rapid=self.feed_rapid.value(),
            spindle_rpm=self.spindle.value(),
            outline_tool_mm=self.outline_tool.value(),
            outline_depth_mm=self.outline_depth.value(),
            drill_depth_mm=self.drill_depth.value(),
            isolation_enabled=self.isolation.isChecked(),
            drilling_enabled=self.drilling.isChecked(),
            outline_enabled=self.outline.isChecked(),
        )

    def apply_settings(self, settings: CamSettings) -> None:
        self.iso_tool.setValue(settings.isolation_tool_mm)
        self.iso_passes.setValue(settings.isolation_passes)
        self.iso_overlap.setValue(settings.isolation_overlap)
        self.cut_depth.setValue(settings.cut_depth_mm)
        self.travel_height.setValue(settings.travel_height_mm)
        self.depth_per_pass.setValue(settings.depth_per_pass_mm)
        self.feed_xy.setValue(settings.feed_xy)
        self.feed_z.setValue(settings.feed_z)
        self.feed_rapid.setValue(settings.feed_rapid)
        self.spindle.setValue(settings.spindle_rpm)
        self.outline_tool.setValue(settings.outline_tool_mm)
        self.outline_depth.setValue(settings.outline_depth_mm)
        self.drill_depth.setValue(settings.drill_depth_mm)
        self.isolation.setChecked(settings.isolation_enabled)
        self.drilling.setChecked(settings.drilling_enabled)
        self.outline.setChecked(settings.outline_enabled)

    def save_settings(self) -> None:
        if self.core.projects.active_dir is None:
            QMessageBox.information(self, "SmartDrill Pro", "Create or open a project first.")
            return
        try:
            settings = self.current_settings()
            self.core.cam.save_settings(self.core.projects.active_dir, settings)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid parameters", str(exc))
            return
        QMessageBox.information(self, "SmartDrill Pro", "CAM parameters saved to this project.")

    def start_job(self) -> None:
        if self.core.projects.active is None:
            QMessageBox.information(self, "SmartDrill Pro", "Create or open a project first.")
            return
        if self._thread is not None and self._thread.isRunning():
            return
        try:
            settings = self.current_settings()
            settings.validate()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid parameters", str(exc))
            return

        self.generate.setEnabled(False)
        self.output.setPlainText("Running FlatCAM headless worker...")
        self._thread = QThread(self)
        worker = CamWorker(self.core, settings)
        worker.moveToThread(self._thread)
        self._thread.started.connect(worker.run_job)
        worker.finished.connect(self._job_finished)
        worker.finished.connect(self._thread.quit)
        worker.finished.connect(worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _job_finished(self, result: CamRunResult) -> None:
        self.generate.setEnabled(True)
        if result.flatcam is None:
            text = "Job did not run:\n- " + "\n- ".join(result.errors)
        else:
            files = "\n".join(f"- {path.name}" for path in result.flatcam.gcode_files) or "- none"
            errors = "\n".join(f"- {item}" for item in result.errors) or "- none"
            text = (
                f"FlatCAM {'succeeded' if result.flatcam.success else 'failed'}.\n\n"
                f"G-code files:\n{files}\n\nMessages:\n{errors}\n\n"
                f"Worker output (tail):\n{result.flatcam.stdout[-3000:]}"
            )
        self.output.setPlainText(text)

    def refresh(self) -> None:
        project = self.core.projects.active
        if project is None:
            self.status.setText("No project is open. Import files before generating toolpaths.")
            return
        project_dir = self.core.projects.active_dir
        settings = self.core.cam.load_settings(project_dir) if project_dir else CamSettings()
        self.apply_settings(settings)
        jobs = project.cam_jobs
        if jobs:
            last = jobs[-1]
            self.status.setText(
                f"Project '{project.name}' | {len(jobs)} CAM job(s) | "
                f"last: {'success' if last.get('success') else 'failed'}"
            )
        else:
            self.status.setText(f"Project '{project.name}' | no CAM jobs yet")
