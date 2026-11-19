"""Phase 5 tests: FlatCAM script generation, planning and result handling."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app.cam.cam_settings import CamSettings
from app.cam.cam_service import CamService
from app.cam.flatcam_adapter import (
    CamOperation,
    FlatcamAdapter,
    FlatcamResult,
    expected_gcode_paths,
)
from app.core.application import Application

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "resources" / "sample_projects" / "simple_board"


def test_script_uses_real_source_files_and_flatcam_commands(tmp_path):
    source = SAMPLE_DIR / "F_Cu.gtl"
    output = tmp_path / "isolation.nc"
    operation = CamOperation("isolation", source, output, "isolation")
    script = FlatcamAdapter().build_script([operation], CamSettings())

    assert "set_sys units MM" in script
    assert "open_gerber {C:/" in script or "open_gerber {" in script
    assert "isolate sd_isolation_1" in script
    assert "cncjob sd_isolation_1_iso" in script
    assert "write_gcode sd_isolation_1_job" in script
    assert "-preamble {" in script and "G21" in script and "G90" in script
    assert "-postamble {" in script and script.strip().endswith("M30\n}")
    # No hardcoded G-code: the worker writes it from the parsed Gerber.
    assert "G1 X" not in script


def test_cam_settings_validation():
    settings = CamSettings(isolation_tool_mm=0)
    with pytest.raises(ValueError):
        settings.validate()
    with pytest.raises(ValueError):
        CamSettings(cut_depth_mm=1.0).validate()


def test_planner_maps_classified_layers_to_operations(tmp_path):
    core = Application(data_dir=tmp_path, simulation=True)
    core.initialize()
    core.projects.create_project("CAM Plan")
    assert core.importer.import_paths([SAMPLE_DIR]).added

    service = CamService(core)
    operations, warnings = service.plan(core.projects.active, core.projects.active_dir_or_raise, CamSettings())
    kinds = {op.kind for op in operations}
    assert kinds == {"isolation", "drilling", "outline"}
    assert all(op.source_path.is_file() for op in operations)
    assert all(op.output_path.parent.name == "gcode" for op in operations)
    assert not warnings
    core.shutdown()


def test_cam_service_persists_job_result(tmp_path, monkeypatch):
    core = Application(data_dir=tmp_path, simulation=True)
    core.initialize()
    core.projects.create_project("CAM Run")
    assert core.importer.import_paths([SAMPLE_DIR]).added
    service = CamService(core)

    def fake_run(script, workdir, timeout_s=300):
        for path in expected_gcode_paths(script):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("G21\nG90\nM30\n", encoding="utf-8")  # test fixture only
        return FlatcamResult(True, script, "worker ok", "", [
            workdir / "gcode" / "isolation.nc",
        ], [])

    monkeypatch.setattr(service.adapter, "run", fake_run)
    result = service.run(CamSettings(), timeout_s=10)
    assert result.success
    assert core.projects.active.cam_jobs
    assert core.projects.active.cam_jobs[-1]["success"] is True
    core.shutdown()


@pytest.mark.integration
def test_real_flatcam_worker_produces_gcode(tmp_path):
    adapter = FlatcamAdapter()
    available, reason = adapter.available
    if not available:
        pytest.skip(reason)
    source = SAMPLE_DIR / "PTH.drl"
    output = tmp_path / "drill_integration.nc"
    script = adapter.build_script([CamOperation("drilling", source, output, "drill")], CamSettings())
    result = adapter.run(script, tmp_path, timeout_s=300)
    assert result.success, "\n".join(result.errors + [result.stdout[-1500:], result.stderr[-1500:]])
    body = output.read_text(encoding="utf-8", errors="replace").upper()
    assert "G21" in body and "G90" in body
    assert "M30" in body
    assert "G00 X" in body and "G01 Z" in body  # real drill motion from the file
