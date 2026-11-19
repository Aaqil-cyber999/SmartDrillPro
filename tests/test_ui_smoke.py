"""Smoke test: the Phase 2 window launches offscreen with full navigation."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PySide6.QtWidgets import QApplication

from app.core.application import Application
from app.ui.main_window import NAVIGATION, MainWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_main_window_opens_and_navigates(qapp, tmp_path):
    core = Application(data_dir=tmp_path, simulation=True)
    core.initialize()
    window = MainWindow(core)

    assert window.windowTitle().startswith("SmartDrill Pro")
    assert window.sidebar.count() == len(NAVIGATION)
    assert window.stack.count() == len(NAVIGATION)
    assert "SIMULATION" in window.mode_label.text()
    assert "Project: none" in window.project_label.text()

    window.navigate_to("New PCB Project")
    assert window.sidebar.currentRow() == 1
    assert window.stack.currentWidget() is window.pages["project"]

    project, _ = core.projects.create_project("UI Smoke Board")
    core.events.emit("project_changed", project)
    assert "UI Smoke Board" in window.project_label.text()

    window.navigate_to("PCB Viewer")
    assert window.stack.currentWidget() is window.pages["viewer"]
    core.shutdown()
