"""Phase 7 tests: simulated grblHAL protocol, RX streaming and job history."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app.core.application import Application
from app.machine.grbl_controller import GrblController, GrblError
from app.machine.serial_transport import SimulatedTransport
from app.core.event_manager import EventManager

GCODE = "\n".join(
    ["G21", "G90"]
    + [f"G1 X{i} Y{i} F100" for i in range(1, 20)]
    + ["M5", "M30"]
)


def make_controller(rx_buffer: int = 128) -> GrblController:
    controller = GrblController(SimulatedTransport(), EventManager(), rx_buffer_bytes=rx_buffer)
    controller.connect()
    return controller


def test_simulated_transport_answers_status_and_commands():
    controller = make_controller()
    assert controller.connected
    status = controller.query_status()
    assert status.state == "Idle"
    controller.home()
    assert controller.query_status().state in {"Home", "Idle"}
    controller.jog("X", 5.0, 400)
    assert controller.query_status().mpos[0] == pytest.approx(5.0)
    controller.feed_hold()
    assert controller.query_status().state == "Hold"
    controller.resume()
    assert controller.query_status().state == "Idle"
    controller.reset()
    assert controller.query_status().mpos == (0.0, 0.0, 0.0)
    details = controller.identify()
    assert any("SmartDrill simulated" in line for line in details)
    assert any(line.startswith("$100=") for line in details)
    controller.disconnect()


def test_rx_buffer_character_counting():
    controller = make_controller(rx_buffer=64)
    lines = [f"G1 X{i} Y{i} F100" for i in range(30)]
    progress: list[tuple[int, int]] = []
    success = controller.stream_lines(lines, on_progress=lambda sent, total, state: progress.append((sent, total)))
    assert success
    assert progress[-1] == (30, 30)
    assert len(controller.transport.entered_lines) == 30 + 6  # streamed lines plus status queries
    controller.disconnect()


def test_oversized_line_rejected():
    controller = make_controller(rx_buffer=32)
    with pytest.raises(GrblError, match="longer than"):
        controller.stream_lines(["G1 X1 Y1 F100 " + "A" * 40])
    controller.disconnect()


def test_machine_service_streams_and_records_job(tmp_path):
    core = Application(data_dir=tmp_path, simulation=True)
    core.initialize()
    core.projects.create_project("Machine Test")
    gcode = core.projects.active_dir_or_raise / "generated" / "gcode" / "job.validated.nc"
    gcode.parent.mkdir(parents=True, exist_ok=True)
    gcode.write_text(GCODE, encoding="utf-8")

    ok, message = core.machine.connect()
    assert ok, message
    with pytest.raises(GrblError):
        core.machine.run_file(gcode, verified=False)
    raw = gcode.with_name("job.nc")
    raw.write_text(GCODE, encoding="utf-8")
    with pytest.raises(GrblError, match="validated"):
        core.machine.run_file(raw, verified=True)
    success, status = core.machine.run_file(gcode, verified=True)
    assert success and status == "completed"
    jobs = core.projects.active.machine_jobs
    assert len(jobs) == 1
    assert jobs[0]["file"] == "job.validated.nc"
    assert jobs[0]["status"] == "completed"
    assert jobs[0]["simulation"] is True
    assert core.machine.status()["state"] == "Idle"
    core.shutdown()


def test_machine_profile_validation_and_persistence(tmp_path):
    core = Application(data_dir=tmp_path, simulation=True)
    core.initialize()
    profile = core.active_profile
    profile.name = "Bench CNC"
    profile.max_travel_mm["X"] = 123.0
    profile.validate()
    core.save_settings()

    restarted = Application(data_dir=tmp_path, simulation=True)
    restarted.initialize()
    assert restarted.active_profile.name == "Bench CNC"
    assert restarted.active_profile.max_travel_mm["X"] == 123.0

    profile.steps_per_mm["Z"] = 0
    with pytest.raises(ValueError, match="steps/mm"):
        profile.validate()
