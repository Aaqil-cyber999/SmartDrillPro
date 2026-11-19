"""Documented GRBL/grblHAL protocol layer (no UGS source code reused).

Only public, documented constants are used: 128-byte receive buffer, ``?``
status query, ``!`` feed hold, ``~`` cycle start, ``$H`` homing and ``\\x18``
soft reset. Streaming uses character counting so the controller is never
overrun.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import re
import time

from app.core.event_manager import EventManager
from app.machine.serial_transport import Transport
from config.application_config import (
    DEFAULT_RX_BUFFER_BYTES,
    DEFAULT_SERIAL_TIMEOUT_S,
    DEFAULT_STATUS_POLL_MS,
)


class GrblError(RuntimeError):
    pass


@dataclass
class MachineStatus:
    state: str = "Disconnected"
    mpos: tuple[float, float, float] = (0.0, 0.0, 0.0)
    feed: float = 0.0
    spindle: float = 0.0

    def as_dict(self) -> dict:
        return {
            "state": self.state,
            "mpos": list(self.mpos),
            "feed": self.feed,
            "spindle": self.spindle,
        }


class GrblController:
    def __init__(
        self,
        transport: Transport,
        events: EventManager | None = None,
        rx_buffer_bytes: int = DEFAULT_RX_BUFFER_BYTES,
        status_poll_ms: int = DEFAULT_STATUS_POLL_MS,
    ) -> None:
        self.transport = transport
        self.events = events or EventManager()
        self.rx_buffer_bytes = max(16, int(rx_buffer_bytes))
        self.status_poll_ms = status_poll_ms
        self.status = MachineStatus()
        self._sent_lengths: deque[int] = deque()
        self._queued_bytes = 0
        self._cancelled = False
        self._pushback: deque[str] = deque()

    # ------------------------------------------------------------------
    # Connection and state
    # ------------------------------------------------------------------
    def connect(self) -> None:
        if self.transport.is_open:
            return
        self.transport.open()
        banner: list[str] = []
        for _ in range(12):
            line = self.transport.read_line(DEFAULT_SERIAL_TIMEOUT_S)
            if not line:
                break
            banner.append(line)
            if line.strip().lower() == "ok":
                break
        self.status = MachineStatus(state="Idle")
        self._emit_log("Connected: " + "; ".join(banner[:3]))
        self.events.emit("machine_status", self.status.as_dict())

    def disconnect(self) -> None:
        self.transport.close()
        self._pushback.clear()
        self.status = MachineStatus(state="Disconnected")
        self._emit_log("Disconnected.")
        self.events.emit("machine_status", self.status.as_dict())

    @property
    def connected(self) -> bool:
        return self.transport.is_open

    def identify(self) -> list[str]:
        """Return `$I` and `$$` replies for machine configuration checks."""
        if not self.connected:
            raise GrblError("Machine is not connected.")
        # A soft reset emits a startup banner; consume it before querying.
        self._pushback.clear()
        while self.transport.read_line(0.05):
            pass
        details: list[str] = []
        for command in ("$I", "$$"):
            self.send_command(command, wait=False)
            deadline = time.monotonic() + DEFAULT_SERIAL_TIMEOUT_S
            while time.monotonic() < deadline:
                line = self._read_response(DEFAULT_SERIAL_TIMEOUT_S).strip()
                if not line:
                    break
                if line.lower() == "ok":
                    break
                details.append(line)
        self._emit_log("Controller identification: " + "; ".join(details[:4]))
        return details

    def query_status(self) -> MachineStatus:
        if not self.connected:
            return self.status
        self.transport.write_line("?")
        deadline = time.monotonic() + DEFAULT_SERIAL_TIMEOUT_S
        deferred: list[str] = []
        while time.monotonic() < deadline:
            line = self._read_response(DEFAULT_SERIAL_TIMEOUT_S).strip()
            if line.startswith("<") and line.endswith(">"):
                self._parse_status(line)
                break
            if not line:
                break
            # 'ok' replies belong to streamed lines and must not be lost here.
            deferred.append(line)
        self._pushback.extend(deferred)
        self.events.emit("machine_status", self.status.as_dict())
        return self.status

    def _parse_status(self, report: str) -> None:
        body = report.strip("<>")
        parts = body.split("|")
        self.status.state = parts[0] if parts else "Unknown"
        for part in parts[1:]:
            if part.startswith("MPos:"):
                values = part[5:].split(",")
                if len(values) >= 3:
                    self.status.mpos = tuple(float(value) for value in values[:3])
            elif part.startswith("FS:"):
                values = part[3:].split(",")
                if len(values) >= 2:
                    self.status.feed, self.status.spindle = float(values[0]), float(values[1])

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    def send_command(self, line: str, wait: bool = True, timeout_s: float = 10.0) -> None:
        if not self.connected:
            raise GrblError("Machine is not connected.")
        line = line.strip()
        if not line:
            return
        self.transport.write_line(line)
        self._emit_log(f"> {line}")
        if wait:
            self._wait_ok(timeout_s)

    def home(self) -> None:
        self.send_command("$H", timeout_s=30.0)
        self.status.state = "Home"
        self.query_status()

    def zero_work(self) -> None:
        self.send_command("G10 L20 P0 X0 Y0 Z0")

    def jog(self, axis: str, distance: float, feed: float) -> None:
        axis = axis.upper()
        if axis not in {"X", "Y", "Z"}:
            raise GrblError(f"Unsupported jog axis: {axis}")
        # grblHAL jogging command; G91 keeps the move relative to current position.
        self.send_command(f"$J=G91 G21 {axis}{distance:.4f} F{feed:.0f}")

    def feed_hold(self) -> None:
        if not self.connected:
            raise GrblError("Machine is not connected.")
        self.transport.write_line("!")
        self.status.state = "Hold"
        self._emit_log("> ! (feed hold)")
        self.events.emit("machine_status", self.status.as_dict())

    def resume(self) -> None:
        if not self.connected:
            raise GrblError("Machine is not connected.")
        self.transport.write_line("~")
        self.status.state = "Run"
        self._emit_log("> ~ (cycle start)")
        self.events.emit("machine_status", self.status.as_dict())

    def reset(self) -> None:
        if not self.connected:
            raise GrblError("Machine is not connected.")
        self.transport.write_line("\x18")
        self._pushback.clear()
        self._sent_lengths.clear()
        self._queued_bytes = 0
        self._cancelled = True
        self.status = MachineStatus(state="Idle")
        self._emit_log("> \\x18 (soft reset)")
        self.events.emit("machine_status", self.status.as_dict())

    # ------------------------------------------------------------------
    # Job streaming
    # ------------------------------------------------------------------
    def stream_lines(self, lines: list[str], on_progress=None, timeout_s: float = 10.0) -> bool:
        """Character-counted streaming. Returns False when cancelled."""
        if not self.connected:
            raise GrblError("Machine is not connected.")
        self._cancelled = False
        self._sent_lengths.clear()
        self._queued_bytes = 0
        active = [line.strip() for line in lines if line.strip() and not line.strip().startswith("(")]
        total = len(active)

        for index, line in enumerate(active, start=1):
            if self._cancelled:
                return False
            length = len(line) + 1
            if length > self.rx_buffer_bytes:
                raise GrblError(f"Line {index} is longer than the {self.rx_buffer_bytes}-byte RX buffer.")
            while self._queued_bytes + length > self.rx_buffer_bytes:
                if self._cancelled:
                    return False
                self._wait_ok(timeout_s)
                self._free_one_line()
            self.transport.write_line(line)
            self._sent_lengths.append(length)
            self._queued_bytes += length
            if index % 5 == 0 or index == total:
                self.query_status()
            if on_progress:
                on_progress(index, total, self.status.state)

        while self._sent_lengths:
            if self._cancelled:
                return False
            self._wait_ok(timeout_s)
            self._free_one_line()
        self.status.state = "Idle"
        self.events.emit("machine_status", self.status.as_dict())
        return not self._cancelled

    def _free_one_line(self) -> None:
        if self._sent_lengths:
            self._queued_bytes -= self._sent_lengths.popleft()

    def _read_response(self, timeout_s: float) -> str:
        if self._pushback:
            return self._pushback.popleft()
        return self.transport.read_line(timeout_s)

    def _wait_ok(self, timeout_s: float) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            line = self._read_response(DEFAULT_SERIAL_TIMEOUT_S).strip()
            if not line:
                continue
            lowered = line.lower()
            if line.startswith("<"):
                self._parse_status(line)
                continue
            if line.startswith("[") or "grbl" in lowered:
                continue
            if lowered == "ok":
                return
            if lowered.startswith("error"):
                raise GrblError(f"Controller rejected a command: {line}")
            self._emit_log(line)
        raise GrblError("Timed out waiting for controller 'ok'.")

    def _emit_log(self, message: str) -> None:
        self.events.emit("machine_log", message)
