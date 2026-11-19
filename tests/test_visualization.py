"""Phase 4 tests: real parsed geometry reaches the QGraphicsScene."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from app.core.event_manager import EventManager
from app.core.project_manager import ProjectManager
from app.file_processing.gerber_parser import GerberParser
from app.services.import_service import ImportService
from app.ui.widgets.pcb_view import PcbView, _polygon_items

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "resources" / "sample_projects" / "simple_board"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_shapely_polygons_become_graphics_items(qapp):
    parsed = GerberParser().parse(SAMPLE_DIR / "F_Cu.gtl")
    items = []
    for feature in parsed.features:
        items.extend(_polygon_items(feature.geometry, "top_copper"))
    assert items
    assert all(not item.polygon().isEmpty() for item in items)


def test_view_renders_imported_project(qapp, tmp_path):
    projects = ProjectManager(tmp_path / "projects", EventManager())
    projects.create_project("Viewer Board")
    importer = ImportService(projects)
    assert importer.import_paths([SAMPLE_DIR]).added

    parsed = importer.parse_project()
    roles = {record.name: record.layer_role for record in projects.active.source_files}
    view = PcbView()
    view.set_layers(parsed, roles)

    assert set(view.layer_groups) == set(parsed)
    assert view.scene.items()
    assert any(
        hasattr(item, "toHtml") and "Board area" in item.toHtml()
        for item in view.scene.items()
    )

    first_name = next(iter(view.layer_groups))
    view.set_layer_visible(first_name, False)
    assert view.layer_groups[first_name].isVisible() is False

    view.set_measure_mode(True)
    assert view.measure_mode is True
    view.set_measure_mode(False)
    assert view.measure_mode is False
