"""Phase 8: editable, UNVERIFIED machine profile and controller identification."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.application import Application
from app.machine.grbl_controller import GrblError
from config.machine_profiles import MachineProfile


class MachineConfigPage(QWidget):
    """Configuration editor. Nothing here claims physical hardware testing."""

    def __init__(self, core: Application) -> None:
        super().__init__()
        self.core = core
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        title = QLabel("Machine configuration")
        title.setObjectName("pageTitle")
        warning = QLabel(
            "UNVERIFIED PROFILE - values below are starting points only. Measure steps/mm, travel, "
            "homing and spindle behaviour on the physical ESP32-S3/grblHAL machine before use."
        )
        warning.setObjectName("noticeText")
        warning.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(warning)

        form = QFormLayout()
        self.name = QLineEdit()
        form.addRow("Profile name", self.name)

        self.steps = self._axis_fields(80.0, 0.1, 10000.0)
        self.travel = self._axis_fields(100.0, 1.0, 5000.0)
        self.feed = self._axis_fields(500.0, 1.0, 10000.0)
        self.accel = self._axis_fields(100.0, 1.0, 5000.0)
        for label, fields in (
            ("Steps/mm", self.steps), ("Travel limit (mm)", self.travel),
            ("Max feed (mm/min)", self.feed), ("Max accel (mm/s²)", self.accel),
        ):
            box = QGroupBox(label)
            axis_layout = QFormLayout(box)
            for axis, spin in fields.items():
                axis_layout.addRow(axis, spin)
            form.addRow(box)

        toggles = QHBoxLayout()
        self.homing = QCheckBox("Homing enabled")
        self.hard_limits = QCheckBox("Hard limits enabled")
        self.soft_limits = QCheckBox("Soft limits enabled")
        self.spindle = QCheckBox("Spindle supported")
        self.calibrated = QCheckBox("I have calibrated this profile on real hardware")
        for widget in (
            self.homing, self.hard_limits, self.soft_limits,
            self.spindle, self.calibrated,
        ):
            toggles.addWidget(widget)
        form.addRow("Machine features", toggles)
        root.addLayout(form)

        buttons = QHBoxLayout()
        save = QPushButton("Save profile")
        save.setObjectName("primaryButton")
        save.clicked.connect(self.save_profile)
        read = QPushButton("Read controller settings ($I / $$)")
        read.clicked.connect(self.read_controller)
        buttons.addWidget(save)
        buttons.addWidget(read)
        buttons.addStretch(1)
        root.addLayout(buttons)

        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Controller identification appears here.")
        root.addWidget(self.details, 1)

        self.load_profile()

    @staticmethod
    def _axis_fields(value: float, minimum: float, maximum: float) -> dict[str, QDoubleSpinBox]:
        fields: dict[str, QDoubleSpinBox] = {}
        for axis in ("X", "Y", "Z"):
            spin = QDoubleSpinBox()
            spin.setRange(minimum, maximum)
            spin.setDecimals(3)
            spin.setValue(value)
            fields[axis] = spin
        return fields

    @staticmethod
    def _set_axis_fields(fields: dict[str, QDoubleSpinBox], values: dict[str, float]) -> None:
        for axis, spin in fields.items():
            spin.setValue(float(values.get(axis, spin.value())))

    @staticmethod
    def _axis_values(fields: dict[str, QDoubleSpinBox]) -> dict[str, float]:
        return {axis: spin.value() for axis, spin in fields.items()}

    def load_profile(self) -> None:
        profile = self.core.active_profile
        self.name.setText(profile.name)
        self._set_axis_fields(self.steps, profile.steps_per_mm)
        self._set_axis_fields(self.travel, profile.max_travel_mm)
        self._set_axis_fields(self.feed, profile.max_feed_mm_min)
        self._set_axis_fields(self.accel, profile.max_accel_mm_s2)
        self.homing.setChecked(profile.homing_enabled)
        self.hard_limits.setChecked(profile.hard_limits_enabled)
        self.soft_limits.setChecked(profile.soft_limits_enabled)
        self.spindle.setChecked(profile.spindle_supported)
        self.calibrated.setChecked(profile.calibrated)

    def current_profile(self) -> MachineProfile:
        return MachineProfile(
            name=self.name.text().strip(),
            calibrated=self.calibrated.isChecked(),
            steps_per_mm=self._axis_values(self.steps),
            max_travel_mm=self._axis_values(self.travel),
            max_feed_mm_min=self._axis_values(self.feed),
            max_accel_mm_s2=self._axis_values(self.accel),
            homing_enabled=self.homing.isChecked(),
            hard_limits_enabled=self.hard_limits.isChecked(),
            soft_limits_enabled=self.soft_limits.isChecked(),
            spindle_supported=self.spindle.isChecked(),
        )

    def save_profile(self) -> None:
        profile = self.current_profile()
        try:
            profile.validate()
        except ValueError as exc:
            QMessageBox.warning(self, "Machine configuration", str(exc))
            return
        self.core.active_profile = profile
        self.core.machine_profiles = [profile]
        self.core.save_settings()
        QMessageBox.information(
            self, "Machine configuration",
            "Profile saved to settings.json. It remains UNVERIFIED until tested on hardware.",
        )

    def read_controller(self) -> None:
        try:
            details = self.core.machine.identify()
        except GrblError as exc:
            QMessageBox.warning(self, "Machine configuration", str(exc))
            return
        self.details.setPlainText("\n".join(details) if details else "No details returned.")
