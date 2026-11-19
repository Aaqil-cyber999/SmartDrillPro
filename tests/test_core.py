"""Core tests that do not require a GUI."""

from __future__ import annotations

import json

from app.core.event_manager import EventManager
from app.core.project_manager import ProjectManager, file_sha256
from app.models.pcb_project import PcbProject
from config.default_settings import AppSettings
from config.machine_profiles import MachineProfile, example_profile


def test_settings_roundtrip(tmp_path):
    settings = AppSettings(units="inch", simulation_mode=False, max_cut_depth_mm=1.5)
    loaded = AppSettings.from_dict(json.loads(json.dumps(settings.to_dict())))
    assert loaded == settings


def test_machine_profile_is_unverified_by_default():
    profile = example_profile()
    assert profile.calibrated is False
    assert "UNVERIFIED" in profile.description
    assert MachineProfile.from_dict(profile.to_dict()).calibrated is False


def test_event_manager_ignores_broken_listeners():
    events = EventManager()
    seen = []
    events.subscribe("test", lambda value: (_ for _ in ()).throw(RuntimeError("boom")))
    events.subscribe("test", seen.append)
    events.emit("test", 42)
    assert seen == [42]


def test_project_create_save_and_load(tmp_path):
    events = EventManager()
    manager = ProjectManager(tmp_path / "projects", events)
    created_events = []
    events.subscribe("project_created", created_events.append)

    project, project_dir = manager.create_project("Test Board")
    assert (project_dir / "project.json").is_file()
    assert (project_dir / "source").is_dir()
    assert (project_dir / "generated" / "gcode").is_dir()
    assert created_events == [project]

    loaded = manager.load(project_dir)
    assert loaded.name == "Test Board"
    assert loaded.id == project.id
    assert loaded.format_version == 1


def test_duplicate_files_are_skipped(tmp_path):
    manager = ProjectManager(tmp_path / "projects", EventManager())
    manager.create_project("Duplicates")

    source_dir = tmp_path / "incoming"
    source_dir.mkdir()
    first = source_dir / "board.gtl"
    first.write_text("G04 first*\nM02*\n", encoding="utf-8")
    copy = source_dir / "copy.gtl"
    copy.write_bytes(first.read_bytes())

    added, skipped = manager.add_source_files([first, copy])
    assert len(added) == 1
    assert len(skipped) == 1
    assert "identical" in skipped[0]
    assert (manager.active_dir_or_raise / "source" / "board.gtl").is_file()


def test_sha256_is_stable(tmp_path):
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")
    assert file_sha256(sample) == file_sha256(sample)
    assert len(file_sha256(sample)) == 64


def test_project_json_roundtrip():
    project = PcbProject(name="Roundtrip")
    loaded = PcbProject.from_dict(json.loads(json.dumps(project.to_dict())))
    assert loaded.id == project.id
    assert loaded.name == project.name
