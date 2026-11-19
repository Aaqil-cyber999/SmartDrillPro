"""Phase 3 tests: validation, parsing, classification and import."""

from __future__ import annotations

from pathlib import Path
import zipfile

from app.core.event_manager import EventManager
from app.core.project_manager import ProjectManager
from app.file_processing.excellon_parser import ExcellonParser
from app.file_processing.file_validator import validate_file, validate_text
from app.file_processing.gerber_parser import GerberParser
from app.file_processing.layer_classifier import classify_layer
from app.services.import_service import ImportService

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "resources" / "sample_projects" / "simple_board"


def test_validation_detects_real_sample_content():
    gerber = validate_file(SAMPLE_DIR / "F_Cu.gtl")
    drill = validate_file(SAMPLE_DIR / "PTH.drl")
    assert gerber.content_type == "gerber" and gerber.valid
    assert drill.content_type == "excellon" and drill.valid
    assert validate_text("hello world\n").valid is False


def test_validation_rejects_empty_and_binary(tmp_path):
    empty = tmp_path / "empty.gbr"
    empty.write_bytes(b"")
    assert validate_file(empty).valid is False
    binary = tmp_path / "random.gbr"
    binary.write_bytes(bytes(range(256)))
    assert validate_file(binary).valid is False


def test_layer_classification():
    assert classify_layer("Edge_Cuts.gm1").role == "outline"
    assert classify_layer("F_Cu.gtl").role == "top_copper"
    assert classify_layer("B_Cu.gbl").role == "bottom_copper"
    assert classify_layer("F_Mask.gts").role == "top_solder_mask"
    assert classify_layer("NPTH.drl").role == "nonplated_drill"
    assert classify_layer("PTH.drl").role == "plated_drill"
    assert classify_layer("mystery.txt").role == "other"


def test_gerber_parser_extracts_geometry():
    parsed = GerberParser().parse(SAMPLE_DIR / "F_Cu.gtl")
    assert parsed.content_type == "gerber"
    assert parsed.feature_count >= 5
    assert parsed.bounds is not None
    assert parsed.bounds[2] > parsed.bounds[0]
    assert all(not feature.geometry.is_empty for feature in parsed.features)


def test_excellon_parser_extracts_drills_and_tools():
    parsed = ExcellonParser().parse(SAMPLE_DIR / "PTH.drl")
    assert parsed.content_type == "excellon"
    assert len(parsed.features) == 3
    assert [tool.diameter_mm for tool in parsed.drill_tools] == [0.8, 1.5]
    assert sum(tool.hole_count for tool in parsed.drill_tools) == 3
    assert all(tool.plated is True for tool in parsed.drill_tools)


def test_import_service_classifies_and_reparses(tmp_path):
    projects = ProjectManager(tmp_path / "projects", EventManager())
    projects.create_project("Import Test")
    importer = ImportService(projects)

    outcome = importer.import_paths([SAMPLE_DIR])
    assert outcome.added, outcome.errors
    assert not outcome.errors
    project = projects.active
    assert project is not None
    roles = {item.name: item.layer_role for item in project.source_files}
    assert roles["F_Cu.gtl"] == "top_copper"
    assert roles["Edge_Cuts.gm1"] == "outline"
    assert roles["PTH.drl"] == "plated_drill"
    assert len(project.layers) == len(project.source_files)

    parsed = importer.parse_project()
    assert "F_Cu.gtl" in parsed
    assert "PTH.drl" in parsed

    assert importer.set_layer_role("F_Cu.gtl", "bottom_copper")
    assert projects.active.source_files[0].layer_role in {"bottom_copper", "top_copper"}
    reloaded = projects.load(projects.active_dir_or_raise)
    assert any(layer.get("source") == "manual" for layer in reloaded.layers)


def test_zip_import_sanitizes_entry_names(tmp_path):
    archive = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.write(SAMPLE_DIR / "F_Cu.gtl", "../evil.gtl")
        handle.write(SAMPLE_DIR / "PTH.drl", "nested/PTH.drl")

    projects = ProjectManager(tmp_path / "projects", EventManager())
    projects.create_project("Zip Test")
    outcome = ImportService(projects).import_paths([archive])
    assert {item.name for item in outcome.added} == {"bundle__evil.gtl", "bundle__PTH.drl"}


def test_invalid_files_are_reported(tmp_path):
    bad = tmp_path / "bad.gbr"
    bad.write_text("this is not a PCB file\n", encoding="utf-8")
    projects = ProjectManager(tmp_path / "projects", EventManager())
    projects.create_project("Bad Files")
    outcome = ImportService(projects).import_paths([bad])
    assert not outcome.added
    assert outcome.skipped
    assert projects.active is not None and not projects.active.source_files
