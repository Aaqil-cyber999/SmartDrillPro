"""Application-facing machine control service."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from app.gcode.gcode_parser import parse_gcode
from app.gcode.gcode_validator import validate_gcode
from app.machine.grbl_controller import GrblController, GrblError
from app.machine.serial_transport import SerialTransport, SimulatedTransport

if TYPE_CHECKING:
    from app.core.application import Application


class MachineService:
    def __init__(self, core: "Application") -> None:
        self.core = core
        self.controller: GrblController | None = None
        self.port = ""

    @property
    def simulation(self) -> bool:
        return self.core.force_simulation or self.core.settings.simulation_mode

    @property
    def connected(self) -> bool:
        return bool(self.controller and self.controller.connected)

    @staticmethod
    def available_ports() -> list[str]:
        try:
            from serial.tools import list_ports

            return [port.device for port in list_ports.comports()]
        except ImportError:
            return []

    def connect(self, port: str = "") -> tuple[bool, str]:
        if self.connected:
            return True, "Already connected."
        transport = (
            SimulatedTransport()
            if self.simulation
            else SerialTransport(port or self.port, self.core.settings.baud_rate)
        )
        controller = GrblController(
            transport,
            self.core.events,
            rx_buffer_bytes=self.core.settings.rx_buffer_bytes,
            status_poll_ms=self.core.settings.status_poll_ms,
        )
        try:
            controller.connect()
        except (OSError, GrblError) as exc:
            return False, f"Connection failed: {exc}"
        self.controller = controller
        self.port = port or self.port
        return True, f"Connected to {transport.description}"

    def disconnect(self) -> str:
        if self.controller:
            self.controller.disconnect()
            self.controller = None
            return "Disconnected."
        return "Already disconnected."

    def require(self) -> GrblController:
        if self.controller is None or not self.controller.connected:
            raise GrblError("Connect to the machine first.")
        return self.controller

    def home(self) -> None:
        self.require().home()

    def zero_work(self) -> None:
        self.require().zero_work()

    def jog(self, axis: str, distance: float, feed: float = 500.0) -> None:
        self.require().jog(axis, distance, feed)

    def hold(self) -> None:
        self.require().feed_hold()

    def resume(self) -> None:
        self.require().resume()

    def reset(self) -> None:
        self.require().reset()

    def status(self) -> dict:
        if self.controller is None:
            return {"state": "Disconnected", "mpos": [0, 0, 0], "feed": 0, "spindle": 0}
        return self.controller.query_status().as_dict()

    def identify(self) -> list[str]:
        """Read controller identification and settings (`$I`, `$$`)."""
        return self.require().identify()

    def run_file(self, path: str | Path, verified: bool) -> tuple[bool, str]:
        """Stream a user-selected, re-validated copy. No implicit demo job."""
        source = Path(path)
        if not verified:
            raise GrblError("Confirm that the toolpath and machine limits were verified.")
        if not source.is_file():
            raise GrblError(f"G-code file does not exist: {source}")
        if not source.name.endswith(".validated.nc"):
            raise GrblError("Only a *.validated.nc copy can be run; create it in G-code Preview first.")
        if self.core.projects.active is None:
            raise GrblError("Open a project before running a job.")

        text = source.read_text(encoding="utf-8", errors="replace")
        report = validate_gcode(
            parse_gcode(text, source=source.name), self.core.settings, self.core.active_profile
        )
        if not report.safe:
            raise GrblError(
                "G-code failed re-validation: " + "; ".join(issue.message for issue in report.errors)
            )

        controller = self.require()
        lines = text.splitlines()
        record = {
            "id": datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"),
            "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "file": source.name,
            "simulation": self.simulation,
            "lines": len(lines),
            "validated": True,
            "estimated_time_s": round(report.estimated_time_s, 1),
            "status": "running",
        }
        project = self.core.projects.active
        project.machine_jobs.append(record)
        self.core.projects.save()

        started = datetime.now(timezone.utc)

        def progress(sent: int, total: int, state: str) -> None:
            self.core.events.emit("job_progress", sent, total, state)

        try:
            finished = controller.stream_lines(lines, on_progress=progress)
            record["status"] = "completed" if finished else "cancelled"
        except GrblError as exc:
            record["status"] = "failed"
            record["error"] = str(exc)
            self.core.events.emit("machine_log", str(exc))
        record["duration_s"] = round((datetime.now(timezone.utc) - started).total_seconds(), 2)
        record["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.core.projects.save()
        self.core.events.emit("job_finished", record)
        return record["status"] == "completed", record["status"]
