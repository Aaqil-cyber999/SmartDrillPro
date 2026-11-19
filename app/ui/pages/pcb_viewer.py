"""PCB visualization page with layer toggles and measurement."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.application import Application
from app.ui.widgets.pcb_view import PcbView


class PcbViewerPage(QWidget):
    def __init__(self, core: Application) -> None:
        super().__init__()
        self.core = core

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        title = QLabel("PCB viewer")
        title.setObjectName("pageTitle")
        self.summary = QLabel("No project is open.")
        self.summary.setObjectName("subtitle")
        root.addWidget(title)
        root.addWidget(self.summary)

        self.view = PcbView()

        toolbar = QHBoxLayout()
        refresh = QPushButton("Refresh geometry")
        refresh.clicked.connect(self.refresh)
        fit = QPushButton("Fit to view")
        fit.clicked.connect(self.view.fit_view)
        zoom_in = QPushButton("Zoom +")
        zoom_in.clicked.connect(lambda: self.view.zoom(1.2))
        zoom_out = QPushButton("Zoom −")
        zoom_out.clicked.connect(lambda: self.view.zoom(1 / 1.2))
        self.measure_button = QPushButton("Measure: off")
        self.measure_button.setCheckable(True)
        self.measure_button.toggled.connect(self._toggle_measure)
        for widget in (refresh, fit, zoom_in, zoom_out, self.measure_button):
            toolbar.addWidget(widget)
        toolbar.addStretch(1)
        self.measure_label = QLabel("Click two points to measure distance.")
        toolbar.addWidget(self.measure_label)
        root.addLayout(toolbar)

        content = QHBoxLayout()
        self.layer_list = QListWidget()
        self.layer_list.setFixedWidth(240)
        self.layer_list.itemChanged.connect(self._layer_toggled)
        self.view.measurement_done.connect(self._measurement_done)
        content.addWidget(self.layer_list)
        content.addWidget(self.view, 1)
        root.addLayout(content, 1)

        for event in ("project_changed", "files_added", "files_removed", "layers_changed"):
            self.core.events.subscribe(event, lambda *_: self.refresh())
        self.refresh()

    def refresh(self) -> None:
        project = self.core.projects.active
        parsed = self.core.importer.parse_project() if project else {}
        roles = {record.name: record.layer_role for record in project.source_files} if project else {}
        self.view.set_layers(parsed, roles)

        self.layer_list.blockSignals(True)
        self.layer_list.clear()
        for name in parsed:
            item = QListWidgetItem(f"{name}  [{roles.get(name, 'other')}]")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.layer_list.addItem(item)
        self.layer_list.blockSignals(False)

        if project is None:
            self.summary.setText("No project is open. Import manufacturing files to see real geometry.")
        elif not parsed:
            self.summary.setText(f"Project '{project.name}' has no parseable files yet.")
        else:
            features = sum(layer.feature_count for layer in parsed.values())
            self.summary.setText(
                f"Project '{project.name}'  |  {len(parsed)} layer(s)  |  {features} geometry feature(s)"
            )

    def _layer_toggled(self, item: QListWidgetItem) -> None:
        name = item.text().split("  [", 1)[0]
        self.view.set_layer_visible(name, item.checkState() == Qt.CheckState.Checked)

    def _toggle_measure(self, enabled: bool) -> None:
        self.view.set_measure_mode(enabled)
        self.measure_button.setText("Measure: on" if enabled else "Measure: off")
        self.measure_label.setText(
            "Click two points to measure distance." if enabled else "Measurement disabled."
        )

    def _measurement_done(self, distance_mm: float) -> None:
        self.measure_label.setText(f"Measured distance: {distance_mm:.2f} mm")
