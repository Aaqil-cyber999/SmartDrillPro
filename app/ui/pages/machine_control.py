"""Machine Control page. Real G-code is streamed only after explicit approval."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QDoubleSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.application import Application
from app.machine.grbl_controller import GrblError
from app.ui.event_bridge import QtEventBridge


class RunWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(bool, str)

    def __init__(self, core: Application, path: Path) -> None:
        super().__init__()
        self.core = core
        self.path = path

    @Slot()
    def run_job(self) -> None:
        try:
            success, status = self.core.machine.run_file(self.path, verified=True)
        except GrblError as exc:
            self.finished.emit(False, f"failed: {exc}")
            return
        self.finished.emit(success, status)


class MachineControlPage(QWidget):
    def __init__(self, core: Application) -> None:
        super().__init__()
        self.core = core
        self._thread: QThread | None = None
        self.bridge = QtEventBridge(core.events, ("job_progress",), self)
        self.bridge.event_received.connect(self._on_bus_event)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)
        title = QLabel("Machine control")
        title.setObjectName("pageTitle")
        self.mode = QLabel("SIMULATION - no physical machine is connected." if core.simulation_mode else "REAL MACHINE MODE - verify everything.")
        self.mode.setObjectName("noticeText")
        root.addWidget(title)
        root.addWidget(self.mode)

        connection = QHBoxLayout()
        self.port_combo = QComboBox()
        self.refresh_ports()
        refresh = QPushButton("Refresh ports")
        refresh.clicked.connect(self.refresh_ports)
        self.connect_button = QPushButton("Connect")
        self.connect_button.setObjectName("primaryButton")
        self.connect_button.clicked.connect(self.toggle_connect)
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.do_disconnect)
        identify = QPushButton("Identify ($I / $$)")
        identify.clicked.connect(self.do_identify)
        self.status_label = QLabel("Status: Disconnected")
        for widget in (
            self.port_combo, refresh, self.connect_button,
            self.disconnect_button, identify, self.status_label,
        ):
            connection.addWidget(widget)
        connection.addStretch(1)
        root.addLayout(connection)

        manual = QGroupBox("Manual commands")
        manual_layout = QGridLayout(manual)
        self.step = QDoubleSpinBox()
        self.step.setRange(0.01, 50.0)
        self.step.setValue(1.0)
        self.feed = QDoubleSpinBox()
        self.feed.setRange(1.0, 5000.0)
        self.feed.setValue(500.0)
        manual_layout.addWidget(QLabel("Jog step (mm)"), 0, 0)
        manual_layout.addWidget(self.step, 0, 1)
        manual_layout.addWidget(QLabel("Jog feed (mm/min)"), 0, 2)
        manual_layout.addWidget(self.feed, 0, 3)
        row = 1
        for axis in ("X", "Y", "Z"):
            manual_layout.addWidget(QLabel(axis), row, 0)
            minus = QPushButton(f"{axis} −")
            plus = QPushButton(f"{axis} +")
            minus.clicked.connect(lambda _checked=False, a=axis: self.do_jog(a, -1))
            plus.clicked.connect(lambda _checked=False, a=axis: self.do_jog(a, 1))
            manual_layout.addWidget(minus, row, 1)
            manual_layout.addWidget(plus, row, 2)
            row += 1
        home = QPushButton("Home ($H)")
        home.clicked.connect(self.safe_call(lambda: self.core.machine.home(), "Homing started."))
        zero = QPushButton("Zero work")
        zero.clicked.connect(self.safe_call(lambda: self.core.machine.zero_work(), "Work zero set."))
        manual_layout.addWidget(home, row, 1)
        manual_layout.addWidget(zero, row, 2)
        root.addWidget(manual)

        job_box = QGroupBox("Job execution")
        job_layout = QFormLayout(job_box)
        self.job_combo = QComboBox()
        self.verified = QCheckBox("I have checked the toolpath, limits and machine state")
        self.run_button = QPushButton("Run selected G-code")
        self.run_button.setObjectName("dangerButton")
        self.run_button.clicked.connect(self.run_job)
        job_layout.addRow("G-code file", self.job_combo)
        job_layout.addRow("Confirmation", self.verified)
        job_layout.addRow(self.run_button)
        controls = QHBoxLayout()
        hold = QPushButton("Feed hold (!)")
        hold.clicked.connect(self.safe_call(lambda: self.core.machine.hold(), "Feed hold sent."))
        resume = QPushButton("Resume (~)")
        resume.clicked.connect(self.safe_call(lambda: self.core.machine.resume(), "Resume sent."))
        reset = QPushButton("Soft reset")
        reset.clicked.connect(self.safe_call(lambda: self.core.machine.reset(), "Soft reset sent."))
        for widget in (hold, resume, reset):
            controls.addWidget(widget)
        job_layout.addRow("Controls", controls)
        self.progress = QProgressBar()
        job_layout.addRow("Progress", self.progress)
        root.addWidget(job_box)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        root.addWidget(self.log, 1)

        for event in ("project_changed", "cam_jobs_changed"):
            self.core.events.subscribe(event, lambda *_: self.refresh_jobs())
        self.refresh_jobs()
        self.update_status()

    def safe_call(self, function, success_message: str):
        def handler() -> None:
            try:
                function()
                self.log.appendPlainText(success_message)
                self.update_status()
            except GrblError as exc:
                QMessageBox.warning(self, "Machine control", str(exc))
                self.log.appendPlainText(f"ERROR: {exc}")
        return handler

    def refresh_ports(self) -> None:
        self.port_combo.clear()
        ports = self.core.machine.available_ports()
        self.port_combo.addItems(ports if ports else ["No serial ports detected"])

    def toggle_connect(self) -> None:
        if self.core.machine.connected:
            self.do_disconnect()
            return
        port = self.port_combo.currentText()
        if "No serial ports" in port:
            port = ""
        ok, message = self.core.machine.connect(port)
        self.log.appendPlainText(message)
        if not ok:
            QMessageBox.warning(self, "Machine control", message)
        self.update_status()

    def do_disconnect(self) -> None:
        self.log.appendPlainText(self.core.machine.disconnect())
        self.update_status()

    def do_identify(self) -> None:
        try:
            details = self.core.machine.identify()
        except GrblError as exc:
            QMessageBox.warning(self, "Machine control", str(exc))
            return
        self.log.appendPlainText("Controller details:\n" + "\n".join(details))

    def _on_bus_event(self, name: str, args: tuple) -> None:
        if name == "job_progress" and len(args) >= 2:
            self._on_progress(args[0], args[1], args[2] if len(args) > 2 else "Run")

    def do_jog(self, axis: str, direction: int) -> None:
        self.safe_call(
            lambda: self.core.machine.jog(axis, self.step.value() * direction, self.feed.value()),
            f"Jog {axis} {direction:+} sent.",
        )()

    def update_status(self) -> None:
        status = self.core.machine.status()
        position = ", ".join(f"{value:.2f}" for value in status["mpos"])
        self.status_label.setText(
            f"Status: {status['state']} | MPos: {position} | F: {status['feed']:.0f}"
        )

    def refresh_jobs(self) -> None:
        self.job_combo.clear()
        directory = self.core.projects.active_dir
        if directory is None:
            return
        gcode_dir = directory / "generated" / "gcode"
        files = sorted(gcode_dir.glob("*.validated.nc")) if gcode_dir.exists() else []
        if not files:
            self.job_combo.addItem("No validated copy - create it in G-code Preview")
        else:
            self.job_combo.addItems([path.name for path in files])

    def run_job(self) -> None:
        if not self.core.machine.connected:
            QMessageBox.information(self, "Machine control", "Connect to the machine first.")
            return
        if not self.verified.isChecked():
            QMessageBox.warning(self, "Machine control", "Confirm the toolpath and limits before running.")
            return
        name = self.job_combo.currentText()
        if not name or "No validated copy" in name:
            QMessageBox.information(
                self, "Machine control",
                "Create a validated copy in G-code Preview before running a job.",
            )
            return
        if self._thread is not None and self._thread.isRunning():
            return
        directory = self.core.projects.active_dir_or_raise / "generated" / "gcode"
        path = directory / name
        self.run_button.setEnabled(False)
        self.progress.setValue(0)
        self.log.appendPlainText(f"Streaming {name} ...")

        self._thread = QThread(self)
        worker = RunWorker(self.core, path)
        worker.moveToThread(self._thread)
        self._thread.started.connect(worker.run_job)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._job_finished)
        worker.finished.connect(self._thread.quit)
        worker.finished.connect(worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_progress(self, sent: int, total: int, state: str) -> None:
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(sent)
        self.status_label.setText(f"Status: {state} | line {sent}/{total}")

    def _job_finished(self, success: bool, status: str) -> None:
        self.run_button.setEnabled(True)
        self.log.appendPlainText(f"Job {status}.")
        self.update_status()
