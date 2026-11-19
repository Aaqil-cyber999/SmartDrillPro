"""Main application window and navigation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QStatusBar,
    QWidget,
)

from app.core.application import Application
from app.ui.pages.cam_processing import CamProcessingPage
from app.ui.pages.dashboard import DashboardPage
from app.ui.pages.file_manager import FileManagerPage
from app.ui.pages.gcode_preview import GcodePreviewPage
from app.ui.pages.job_history import JobHistoryPage
from app.ui.pages.machine_config import MachineConfigPage
from app.ui.pages.machine_control import MachineControlPage
from app.ui.pages.settings_page import SettingsPage
from app.ui.pages.pcb_viewer import PcbViewerPage
from app.ui.pages.project_page import ProjectPage
from config.application_config import APP_NAME, APP_VERSION, PROJECT_ROOT

NAVIGATION: list[tuple[str, str]] = [
    ("Dashboard", "dashboard"),
    ("New PCB Project", "project"),
    ("File Manager", "files"),
    ("PCB Viewer", "viewer"),
    ("CAM Processing", "cam"),
    ("G-code Preview", "gcode"),
    ("Machine Control", "machine"),
    ("Job History", "history"),
    ("Machine Configuration", "machine_config"),
    ("Settings", "settings"),
]


class MainWindow(QMainWindow):
    def __init__(self, core: Application) -> None:
        super().__init__()
        self.core = core
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1280, 800)
        self.setMinimumSize(1024, 640)

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(230)
        for label, _ in NAVIGATION:
            item = QListWidgetItem(label)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.sidebar.addItem(item)
        self.sidebar.currentRowChanged.connect(self.show_page)
        main_layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.pages: dict[str, QWidget] = {}
        self.pages["dashboard"] = DashboardPage()
        self.pages["dashboard"].navigate_requested.connect(self.navigate_to)
        self.pages["project"] = ProjectPage(core)
        self.pages["files"] = FileManagerPage(core)
        self.pages["viewer"] = PcbViewerPage(core)
        self.pages["cam"] = CamProcessingPage(core)
        self.pages["gcode"] = GcodePreviewPage(core)
        self.pages["machine"] = MachineControlPage(core)
        self.pages["history"] = JobHistoryPage(core)
        self.pages["machine_config"] = MachineConfigPage(core)
        self.pages["settings"] = SettingsPage(core)
        for _, key in NAVIGATION:
            self.stack.addWidget(self.pages[key])
        main_layout.addWidget(self.stack)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.mode_label = QLabel()
        self.project_label = QLabel()
        self.status_bar.addPermanentWidget(self.project_label)
        self.status_bar.addPermanentWidget(self.mode_label)
        self.update_status()

        core.events.subscribe("project_changed", lambda *_: self.update_status())
        core.events.subscribe("settings_changed", lambda *_: self.update_status())

        self.sidebar.setCurrentRow(0)
        self.show_page(0)
        self.apply_styles()

    def navigate_to(self, label: str) -> None:
        for index, (name, _) in enumerate(NAVIGATION):
            if name == label:
                self.sidebar.setCurrentRow(index)
                return

    def show_page(self, index: int) -> None:
        if 0 <= index < len(NAVIGATION):
            self.stack.setCurrentIndex(index)

    def update_status(self) -> None:
        mode = "SIMULATION" if self.core.simulation_mode else "REAL MACHINE"
        self.mode_label.setText(f"Mode: {mode}")
        project = self.core.projects.active
        self.project_label.setText(f"Project: {project.name}" if project else "Project: none")

    def apply_styles(self) -> None:
        stylesheet_path = PROJECT_ROOT / "resources" / "styles" / "app.qss"
        if stylesheet_path.is_file():
            self.setStyleSheet(stylesheet_path.read_text(encoding="utf-8"))
